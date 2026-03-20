package handler

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/middleware"
	"daidai-panel/model"
	"daidai-panel/pkg/cron"
	"daidai-panel/pkg/response"
	"daidai-panel/service"

	"github.com/gin-gonic/gin"
)

type TaskHandler struct{}

func NewTaskHandler() *TaskHandler {
	return &TaskHandler{}
}

func (h *TaskHandler) List(c *gin.Context) {
	keyword := c.Query("keyword")
	statusStr := c.Query("status")
	label := c.Query("label")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	query := database.DB.Model(&model.Task{})

	if keyword != "" {
		like := "%" + keyword + "%"
		query = query.Where("name LIKE ? OR command LIKE ?", like, like)
	}
	if statusStr != "" {
		status, err := strconv.ParseFloat(statusStr, 64)
		if err == nil {
			query = query.Where("status = ?", status)
		}
	}
	if label != "" {
		query = query.Where("labels LIKE ?", "%"+label+"%")
	}

	var total int64
	query.Count(&total)

	var tasks []model.Task
	query.Order("is_pinned DESC, sort_order ASC, created_at DESC").
		Offset((page - 1) * pageSize).Limit(pageSize).Find(&tasks)

	data := make([]map[string]interface{}, len(tasks))
	for i, t := range tasks {
		d := t.ToDict()
		if t.Status != model.TaskStatusDisabled && t.CronExpression != "" {
			nextTimes := cron.NextRunTimes(t.CronExpression, 1)
			if len(nextTimes) > 0 {
				d["next_run_at"] = nextTimes[0]
			}
		}
		data[i] = d
	}

	response.Paginated(c, data, total, page, pageSize)
}

func (h *TaskHandler) Create(c *gin.Context) {
	var req struct {
		Name                   string   `json:"name" binding:"required"`
		Command                string   `json:"command" binding:"required"`
		CronExpression         string   `json:"cron_expression" binding:"required"`
		Timeout                *int     `json:"timeout"`
		MaxRetries             *int     `json:"max_retries"`
		RetryInterval          *int     `json:"retry_interval"`
		NotifyOnFailure        *bool    `json:"notify_on_failure"`
		NotifyOnSuccess        *bool    `json:"notify_on_success"`
		Labels                 []string `json:"labels"`
		DependsOn              *uint    `json:"depends_on"`
		TaskBefore             *string  `json:"task_before"`
		TaskAfter              *string  `json:"task_after"`
		AllowMultipleInstances *bool    `json:"allow_multiple_instances"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	task := model.Task{
		Name:            req.Name,
		Command:         req.Command,
		CronExpression:  req.CronExpression,
		Status:          model.TaskStatusEnabled,
		Timeout:         86400,
		RetryInterval:   60,
		NotifyOnFailure: true,
	}

	if req.Timeout != nil {
		task.Timeout = *req.Timeout
	}
	if req.MaxRetries != nil {
		task.MaxRetries = *req.MaxRetries
	}
	if req.RetryInterval != nil {
		task.RetryInterval = *req.RetryInterval
	}
	if req.NotifyOnFailure != nil {
		task.NotifyOnFailure = *req.NotifyOnFailure
	}
	if req.NotifyOnSuccess != nil {
		task.NotifyOnSuccess = *req.NotifyOnSuccess
	}
	if req.Labels != nil {
		task.SetLabelsFromSlice(req.Labels)
	}
	if req.DependsOn != nil {
		task.DependsOn = req.DependsOn
	}
	if req.TaskBefore != nil {
		task.TaskBefore = req.TaskBefore
	}
	if req.TaskAfter != nil {
		task.TaskAfter = req.TaskAfter
	}
	if req.AllowMultipleInstances != nil {
		task.AllowMultipleInstances = *req.AllowMultipleInstances
	}

	if err := database.DB.Create(&task).Error; err != nil {
		response.InternalError(c, "创建任务失败")
		return
	}

	service.GetSchedulerV2().AddJob(&task)

	response.Created(c, gin.H{
		"message": "创建成功",
		"data":    task.ToDict(),
	})
}

func (h *TaskHandler) Update(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}

	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	if labels, ok := req["labels"].([]interface{}); ok {
		strs := make([]string, len(labels))
		for i, l := range labels {
			strs[i] = fmt.Sprintf("%v", l)
		}
		req["labels"] = strings.Join(strs, ",")
	}

	allowedFields := map[string]bool{
		"name": true, "command": true, "cron_expression": true,
		"timeout": true, "max_retries": true, "retry_interval": true,
		"notify_on_failure": true, "notify_on_success": true, "labels": true, "depends_on": true,
		"sort_order": true, "task_before": true, "task_after": true,
		"allow_multiple_instances": true,
	}

	updates := make(map[string]interface{})
	for k, v := range req {
		if allowedFields[k] {
			updates[k] = v
		}
	}

	if len(updates) > 0 {
		database.DB.Model(&task).Updates(updates)
	}

	database.DB.First(&task, taskID)
	service.GetSchedulerV2().UpdateJob(&task)

	response.Success(c, gin.H{
		"message": "task updated",
		"data":    task.ToDict(),
	})
}

func (h *TaskHandler) Delete(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}

	service.GetSchedulerV2().RemoveJob(uint(taskID))
	database.DB.Where("task_id = ?", taskID).Delete(&model.TaskLog{})
	database.DB.Delete(&task)

	response.Success(c, gin.H{"message": "删除成功"})
}

func (h *TaskHandler) Run(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}

	if task.Status == model.TaskStatusRunning {
		response.BadRequest(c, "任务正在运行中")
		return
	}

	database.DB.Model(&task).Update("status", model.TaskStatusRunning)

	service.GetSchedulerV2().RunNow(uint(taskID))
	response.Success(c, gin.H{"message": "任务已启动"})
}

func (h *TaskHandler) Stop(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}

	stopped := service.GetTaskExecutor().StopTask(uint(taskID))

	if !stopped {
		if s := service.GetScheduler(); s != nil {
			stopped = s.StopRunningTask(uint(taskID))
		}
	}

	if task.PID != nil && *task.PID > 0 {
		service.KillProcessByPid(*task.PID)
	}

	database.DB.Model(&task).Updates(map[string]interface{}{
		"status":   model.TaskStatusEnabled,
		"pid":      nil,
		"log_path": nil,
	})

	var runningLog model.TaskLog
	if err := database.DB.Where("task_id = ? AND status = ?", taskID, model.LogStatusRunning).
		Order("started_at DESC").First(&runningLog).Error; err == nil {
		failedStatus := model.LogStatusFailed
		now := time.Now()
		database.DB.Model(&runningLog).Updates(map[string]interface{}{
			"status":   failedStatus,
			"ended_at": now,
		})
	}

	response.Success(c, gin.H{"message": "任务已停止"})
}

func (h *TaskHandler) Enable(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}
	task.Status = model.TaskStatusEnabled
	database.DB.Save(&task)
	service.GetSchedulerV2().AddJob(&task)
	response.Success(c, gin.H{"message": "已启用", "data": task.ToDict()})
}

func (h *TaskHandler) Disable(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}
	task.Status = model.TaskStatusDisabled
	database.DB.Save(&task)
	service.GetSchedulerV2().RemoveJob(uint(taskID))
	response.Success(c, gin.H{"message": "已禁用", "data": task.ToDict()})
}

func (h *TaskHandler) Pin(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	database.DB.Model(&model.Task{}).Where("id = ?", taskID).Update("is_pinned", true)
	response.Success(c, gin.H{"message": "已置顶"})
}

func (h *TaskHandler) Unpin(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	database.DB.Model(&model.Task{}).Where("id = ?", taskID).Update("is_pinned", false)
	response.Success(c, gin.H{"message": "已取消置顶"})
}

func (h *TaskHandler) Copy(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	var task model.Task
	if err := database.DB.First(&task, taskID).Error; err != nil {
		response.NotFound(c, "任务不存在")
		return
	}

	newTask := model.Task{
		Name:                   task.Name + " (副本)",
		Command:                task.Command,
		CronExpression:         task.CronExpression,
		Status:                 model.TaskStatusDisabled,
		Labels:                 task.Labels,
		Timeout:                task.Timeout,
		MaxRetries:             task.MaxRetries,
		RetryInterval:          task.RetryInterval,
		NotifyOnFailure:        task.NotifyOnFailure,
		NotifyOnSuccess:        task.NotifyOnSuccess,
		DependsOn:              task.DependsOn,
		TaskBefore:             task.TaskBefore,
		TaskAfter:              task.TaskAfter,
		AllowMultipleInstances: task.AllowMultipleInstances,
	}
	database.DB.Create(&newTask)
	response.Created(c, gin.H{"message": "复制成功", "data": newTask.ToDict()})
}

func (h *TaskHandler) Batch(c *gin.Context) {
	var req struct {
		IDs    []uint `json:"ids" binding:"required"`
		Action string `json:"action" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	sch := service.GetSchedulerV2()
	count := 0

	for _, id := range req.IDs {
		var task model.Task
		if database.DB.First(&task, id).Error != nil {
			continue
		}

		switch req.Action {
		case "enable":
			task.Status = model.TaskStatusEnabled
			database.DB.Save(&task)
			sch.AddJob(&task)
		case "disable":
			task.Status = model.TaskStatusDisabled
			database.DB.Save(&task)
			sch.RemoveJob(id)
		case "delete":
			sch.RemoveJob(id)
			database.DB.Where("task_id = ?", id).Delete(&model.TaskLog{})
			database.DB.Delete(&task)
		case "run":
			if task.Status != model.TaskStatusRunning {
				sch.RunNow(id)
			}
		case "pin":
			database.DB.Model(&task).Update("is_pinned", true)
		case "unpin":
			database.DB.Model(&task).Update("is_pinned", false)
		}
		count++
	}

	response.Success(c, gin.H{"message": fmt.Sprintf("批量%s: %d 个任务", req.Action, count), "count": count})
}

func (h *TaskHandler) BatchEnable(c *gin.Context) {
	var req struct {
		TaskIDs []uint `json:"task_ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	sch := service.GetSchedulerV2()
	count := 0
	for _, id := range req.TaskIDs {
		var task model.Task
		if database.DB.First(&task, id).Error != nil {
			continue
		}
		task.Status = model.TaskStatusEnabled
		database.DB.Save(&task)
		sch.AddJob(&task)
		count++
	}
	response.Success(c, gin.H{"message": fmt.Sprintf("已启用 %d 个任务", count), "success_count": count})
}

func (h *TaskHandler) BatchDisable(c *gin.Context) {
	var req struct {
		TaskIDs []uint `json:"task_ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	sch := service.GetSchedulerV2()
	count := 0
	for _, id := range req.TaskIDs {
		var task model.Task
		if database.DB.First(&task, id).Error != nil {
			continue
		}
		task.Status = model.TaskStatusDisabled
		database.DB.Save(&task)
		sch.RemoveJob(id)
		count++
	}
	response.Success(c, gin.H{"message": fmt.Sprintf("已禁用 %d 个任务", count), "success_count": count})
}

func (h *TaskHandler) BatchDelete(c *gin.Context) {
	var req struct {
		TaskIDs []uint `json:"task_ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	sch := service.GetSchedulerV2()
	count := 0
	for _, id := range req.TaskIDs {
		sch.RemoveJob(id)
		database.DB.Where("task_id = ?", id).Delete(&model.TaskLog{})
		database.DB.Where("id = ?", id).Delete(&model.Task{})
		count++
	}
	response.Success(c, gin.H{"message": fmt.Sprintf("已删除 %d 个任务", count), "count": count})
}

func (h *TaskHandler) BatchRun(c *gin.Context) {
	var req struct {
		TaskIDs []uint `json:"task_ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	if len(req.TaskIDs) > 10 {
		response.BadRequest(c, "批量运行最多 10 个任务")
		return
	}

	sch := service.GetSchedulerV2()
	count := 0
	for _, id := range req.TaskIDs {
		var task model.Task
		if database.DB.First(&task, id).Error != nil {
			continue
		}
		if task.Status != model.TaskStatusRunning {
			sch.RunNow(id)
			count++
		}
	}
	response.Success(c, gin.H{"message": fmt.Sprintf("已启动 %d 个任务", count), "count": count})
}

func (h *TaskHandler) LatestLog(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var taskLog model.TaskLog
	if err := database.DB.Where("task_id = ?", taskID).Order("started_at DESC").First(&taskLog).Error; err != nil {
		response.NotFound(c, "暂无日志")
		return
	}

	result := taskLog.ToDict()
	if taskLog.Content != "" {
		decompressed, err := service.DecompressFromBase64(taskLog.Content)
		if err == nil {
			result["content"] = decompressed
		}
	} else if taskLog.LogPath != nil {
		content, err := service.ReadLogFile(*taskLog.LogPath, config.C.Data.LogDir)
		if err == nil {
			result["content"] = content
		}
	}

	response.Success(c, result)
}

func (h *TaskHandler) LiveLogs(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var task model.Task
	database.DB.First(&task, taskID)

	done := task.Status != model.TaskStatusRunning

	var lines []string
	mgr := service.GetTinyLogManager()
	tl := mgr.FindByTaskID(uint(taskID))
	if tl != nil {
		data, _ := tl.ReadLastLines(200)
		if len(data) > 0 {
			lines = strings.Split(string(data), "\n")
		}
	}

	if lines == nil {
		lines = []string{}
	}

	response.Success(c, gin.H{
		"logs":   lines,
		"done":   done,
		"status": task.Status,
	})
}

func (h *TaskHandler) LogFiles(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	files := service.ListLogFiles(uint(taskID), config.C.Data.LogDir)
	response.Success(c, files)
}

func (h *TaskHandler) LogFileContent(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	filename := c.Param("filename")

	logPath := fmt.Sprintf("task_%d/%s", taskID, filename)
	content, err := service.ReadLogFile(logPath, config.C.Data.LogDir)
	if err != nil {
		response.NotFound(c, "日志文件不存在")
		return
	}

	response.Success(c, gin.H{"filename": filename, "content": content})
}

func (h *TaskHandler) DeleteLogFile(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	filename := c.Param("filename")

	logPath := fmt.Sprintf("task_%d/%s", taskID, filename)
	if err := service.DeleteLogFile(logPath, config.C.Data.LogDir); err != nil {
		response.InternalError(c, "删除日志文件失败")
		return
	}
	response.Success(c, gin.H{"message": "日志文件已删除"})
}

func (h *TaskHandler) DownloadLogFile(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	filename := c.Param("filename")

	logPath := fmt.Sprintf("task_%d/%s", taskID, filename)
	content, err := service.ReadLogFile(logPath, config.C.Data.LogDir)
	if err != nil {
		response.NotFound(c, "日志文件不存在")
		return
	}

	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=%s", filename))
	c.Data(http.StatusOK, "text/plain; charset=utf-8", []byte(content))
}

func (h *TaskHandler) CleanLogs(c *gin.Context) {
	daysStr := c.DefaultQuery("days", "7")
	days, _ := strconv.Atoi(daysStr)
	if days < 1 {
		days = 7
	}

	count := service.CleanOldLogs(config.C.Data.LogDir, days)
	response.Success(c, gin.H{"message": fmt.Sprintf("已清理 %d 个日志文件", count)})
}

func (h *TaskHandler) Export(c *gin.Context) {
	var tasks []model.Task
	database.DB.Find(&tasks)

	data := make([]map[string]interface{}, len(tasks))
	for i, t := range tasks {
		data[i] = map[string]interface{}{
			"name":                     t.Name,
			"command":                  t.Command,
			"cron_expression":          t.CronExpression,
			"status":                   t.Status,
			"labels":                   t.GetLabels(),
			"timeout":                  t.Timeout,
			"max_retries":              t.MaxRetries,
			"retry_interval":           t.RetryInterval,
			"notify_on_failure":        t.NotifyOnFailure,
			"notify_on_success":        t.NotifyOnSuccess,
			"depends_on":               t.DependsOn,
			"sort_order":               t.SortOrder,
			"task_before":              t.TaskBefore,
			"task_after":               t.TaskAfter,
			"allow_multiple_instances": t.AllowMultipleInstances,
		}
	}
	response.Success(c, gin.H{"data": data})
}

func (h *TaskHandler) Import(c *gin.Context) {
	var req struct {
		Tasks []map[string]interface{} `json:"tasks" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	imported := 0
	errors := make([]string, 0)

	for i, t := range req.Tasks {
		name, _ := t["name"].(string)
		command, _ := t["command"].(string)
		cronExpr, _ := t["cron_expression"].(string)

		if name == "" || command == "" || cronExpr == "" {
			errors = append(errors, fmt.Sprintf("任务 %d: 缺少必填字段", i+1))
			continue
		}

		result := cron.Parse(cronExpr)
		if !result.Valid {
			errors = append(errors, fmt.Sprintf("任务 %d: 无效的 cron 表达式", i+1))
			continue
		}

		task := model.Task{
			Name:            name,
			Command:         command,
			CronExpression:  cronExpr,
			Status:          model.TaskStatusDisabled,
			Timeout:         86400,
			RetryInterval:   60,
			NotifyOnFailure: true,
		}

		if v, ok := t["timeout"].(float64); ok {
			task.Timeout = int(v)
		}
		if v, ok := t["max_retries"].(float64); ok {
			task.MaxRetries = int(v)
		}
		if v, ok := t["retry_interval"].(float64); ok {
			task.RetryInterval = int(v)
		}
		if v, ok := t["notify_on_failure"].(bool); ok {
			task.NotifyOnFailure = v
		}
		if v, ok := t["notify_on_success"].(bool); ok {
			task.NotifyOnSuccess = v
		}
		if labels, ok := t["labels"].([]interface{}); ok {
			strs := make([]string, len(labels))
			for j, l := range labels {
				strs[j] = fmt.Sprintf("%v", l)
			}
			task.SetLabelsFromSlice(strs)
		}
		if v, ok := t["task_before"].(string); ok {
			task.TaskBefore = &v
		}
		if v, ok := t["task_after"].(string); ok {
			task.TaskAfter = &v
		}

		if err := database.DB.Create(&task).Error; err != nil {
			errors = append(errors, fmt.Sprintf("task %d: %s", i+1, err.Error()))
			continue
		}
		imported++
	}

	if imported == 0 && len(errors) > 0 {
		response.BadRequest(c, "没有成功导入任何任务")
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"message": fmt.Sprintf("成功导入 %d 个任务", imported),
		"errors":  errors,
	})
}

func (h *TaskHandler) CronParse(c *gin.Context) {
	var req struct {
		Expression string `json:"expression" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	result := cron.Parse(req.Expression)
	if !result.Valid {
		response.Success(c, gin.H{
			"is_valid": false,
			"error":    result.Error,
		})
		return
	}

	nextTimes := cron.NextRunTimes(req.Expression, 5)
	timeStrs := make([]string, len(nextTimes))
	for i, t := range nextTimes {
		timeStrs[i] = t.Format(time.RFC3339)
	}

	format := "标准格式 (5位)"
	if result.HasSecond {
		format = "扩展格式 (6位含秒)"
	}

	response.Success(c, gin.H{
		"is_valid":       true,
		"description":    result.Description,
		"next_run_times": timeStrs,
		"format":         format,
	})
}

func (h *TaskHandler) CronTemplates(c *gin.Context) {
	response.Success(c, cron.GetTemplates())
}

func (h *TaskHandler) Stats(c *gin.Context) {
	taskID, _ := strconv.ParseUint(c.Param("id"), 10, 32)
	daysStr := c.DefaultQuery("days", "7")
	days, _ := strconv.Atoi(daysStr)
	if days < 1 {
		days = 7
	}

	stats := service.GetTaskStats(uint(taskID), days)
	if stats == nil {
		response.NotFound(c, "任务不存在")
		return
	}
	response.Success(c, stats)
}

func (h *TaskHandler) RegisterRoutes(r *gin.RouterGroup) {
	tasks := r.Group("/tasks", middleware.JWTAuth())
	{
		tasks.GET("", h.List)
		tasks.POST("", h.Create)
		tasks.PUT("/:id", h.Update)
		tasks.DELETE("/:id", h.Delete)
		tasks.PUT("/:id/run", h.Run)
		tasks.PUT("/:id/stop", h.Stop)
		tasks.PUT("/:id/enable", h.Enable)
		tasks.PUT("/:id/disable", h.Disable)
		tasks.PUT("/:id/pin", h.Pin)
		tasks.PUT("/:id/unpin", h.Unpin)
		tasks.POST("/:id/copy", h.Copy)
		tasks.GET("/:id/latest-log", h.LatestLog)
		tasks.GET("/:id/live-logs", h.LiveLogs)
		tasks.GET("/:id/log-files", h.LogFiles)
		tasks.GET("/:id/log-files/:filename", h.LogFileContent)
		tasks.DELETE("/:id/log-files/:filename", h.DeleteLogFile)
		tasks.GET("/:id/log-files/:filename/download", h.DownloadLogFile)
		tasks.GET("/:id/stats", h.Stats)
		tasks.PUT("/batch", h.Batch)
		tasks.PUT("/batch/enable", h.BatchEnable)
		tasks.PUT("/batch/disable", h.BatchDisable)
		tasks.DELETE("/batch/delete", h.BatchDelete)
		tasks.POST("/batch/run", h.BatchRun)
		tasks.DELETE("/clean-logs", h.CleanLogs)
		tasks.GET("/export", h.Export)
		tasks.POST("/import", h.Import)
		tasks.POST("/cron/parse", h.CronParse)
		tasks.GET("/cron/templates", h.CronTemplates)
	}
}

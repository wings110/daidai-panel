package handler

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/middleware"
	"daidai-panel/model"
	"daidai-panel/pkg/response"

	"github.com/gin-gonic/gin"
)

type depLogBroadcaster struct {
	mu   sync.RWMutex
	subs map[chan string]struct{}
}

var (
	depLogStreams   = make(map[uint]*depLogBroadcaster)
	depLogStreamsMu sync.RWMutex
)

func getOrCreateBroadcaster(id uint) *depLogBroadcaster {
	depLogStreamsMu.Lock()
	defer depLogStreamsMu.Unlock()
	if b, ok := depLogStreams[id]; ok {
		return b
	}
	b := &depLogBroadcaster{subs: make(map[chan string]struct{})}
	depLogStreams[id] = b
	return b
}

func removeBroadcaster(id uint) {
	depLogStreamsMu.Lock()
	defer depLogStreamsMu.Unlock()
	if b, ok := depLogStreams[id]; ok {
		b.mu.Lock()
		for ch := range b.subs {
			close(ch)
		}
		b.mu.Unlock()
		delete(depLogStreams, id)
	}
}

func (b *depLogBroadcaster) subscribe() chan string {
	ch := make(chan string, 64)
	b.mu.Lock()
	b.subs[ch] = struct{}{}
	b.mu.Unlock()
	return ch
}

func (b *depLogBroadcaster) unsubscribe(ch chan string) {
	b.mu.Lock()
	delete(b.subs, ch)
	b.mu.Unlock()
}

func (b *depLogBroadcaster) broadcast(line string) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	for ch := range b.subs {
		select {
		case ch <- line:
		default:
		}
	}
}

func (b *depLogBroadcaster) done() {
	b.mu.RLock()
	defer b.mu.RUnlock()
	for ch := range b.subs {
		select {
		case ch <- "\x00DONE":
		default:
		}
	}
}

type DepsHandler struct{}

func NewDepsHandler() *DepsHandler {
	return &DepsHandler{}
}

func (h *DepsHandler) List(c *gin.Context) {
	depType := c.DefaultQuery("type", "nodejs")

	validTypes := map[string]bool{
		model.DepTypeNodeJS: true,
		model.DepTypePython: true,
		model.DepTypeLinux:  true,
	}
	if !validTypes[depType] {
		response.BadRequest(c, "无效的依赖类型")
		return
	}

	var deps []model.Dependency
	database.DB.Where("type = ?", depType).Order("created_at DESC").Find(&deps)

	data := make([]map[string]interface{}, len(deps))
	for i, d := range deps {
		data[i] = d.ToDict()
	}

	response.Success(c, gin.H{"data": data, "total": len(data)})
}

func (h *DepsHandler) Create(c *gin.Context) {
	var req struct {
		Type  string   `json:"type" binding:"required"`
		Names []string `json:"names" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	validTypes := map[string]bool{
		model.DepTypeNodeJS: true,
		model.DepTypePython: true,
		model.DepTypeLinux:  true,
	}
	if !validTypes[req.Type] {
		response.BadRequest(c, "无效的依赖类型")
		return
	}

	created := []map[string]interface{}{}
	for _, name := range req.Names {
		name = strings.TrimSpace(name)
		if name == "" {
			continue
		}
		if strings.ContainsAny(name, ";|&`$(){}") {
			continue
		}

		dep := model.Dependency{
			Type:   req.Type,
			Name:   name,
			Status: model.DepStatusInstalling,
		}
		if err := database.DB.Create(&dep).Error; err != nil {
			continue
		}
		created = append(created, dep.ToDict())

		go installDependency(dep.ID, req.Type, name)
	}

	response.Created(c, gin.H{
		"message": fmt.Sprintf("已提交 %d 个依赖安装", len(created)),
		"data":    created,
	})
}

func (h *DepsHandler) Delete(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var dep model.Dependency
	if err := database.DB.First(&dep, id).Error; err != nil {
		response.NotFound(c, "依赖不存在")
		return
	}

	if dep.Status == model.DepStatusInstalling || dep.Status == model.DepStatusRemoving {
		response.BadRequest(c, "依赖正在处理中")
		return
	}

	if c.Query("force") == "true" {
		database.DB.Delete(&dep)
		go forceUninstallDependency(dep.Type, dep.Name)
		response.Success(c, gin.H{"message": "强制卸载中"})
		return
	}

	database.DB.Model(&dep).Update("status", model.DepStatusRemoving)

	go uninstallDependency(dep.ID, dep.Type, dep.Name)

	response.Success(c, gin.H{"message": "卸载中"})
}

func (h *DepsHandler) BatchDelete(c *gin.Context) {
	var req struct {
		IDs []uint `json:"ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil || len(req.IDs) == 0 {
		response.BadRequest(c, "请求参数错误")
		return
	}

	var deps []model.Dependency
	database.DB.Where("id IN ? AND status NOT IN ?", req.IDs, []string{model.DepStatusInstalling, model.DepStatusRemoving}).Find(&deps)

	for _, dep := range deps {
		database.DB.Delete(&dep)
		go forceUninstallDependency(dep.Type, dep.Name)
	}

	response.Success(c, gin.H{"message": fmt.Sprintf("已提交 %d 个依赖卸载", len(deps))})
}

func (h *DepsHandler) GetStatus(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var dep model.Dependency
	if err := database.DB.First(&dep, id).Error; err != nil {
		response.NotFound(c, "依赖不存在")
		return
	}

	response.Success(c, gin.H{"data": dep.ToDictWithLog()})
}

func (h *DepsHandler) LogStream(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	tokenStr := c.Query("token")
	if tokenStr == "" {
		c.JSON(401, gin.H{"error": "缺少令牌"})
		return
	}
	claims, err := middleware.ParseToken(tokenStr)
	if err != nil || claims.TokenType != "access" {
		c.JSON(401, gin.H{"error": "令牌无效"})
		return
	}

	var dep model.Dependency
	if err := database.DB.First(&dep, id).Error; err != nil {
		c.JSON(404, gin.H{"error": "依赖不存在"})
		return
	}

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")

	if dep.Log != "" {
		for _, line := range strings.Split(dep.Log, "\n") {
			if line != "" {
				fmt.Fprintf(c.Writer, "data: %s\n\n", line)
			}
		}
		c.Writer.Flush()
	}

	if dep.Status != model.DepStatusInstalling && dep.Status != model.DepStatusRemoving {
		fmt.Fprintf(c.Writer, "event: done\ndata: %s\n\n", dep.Status)
		c.Writer.Flush()
		return
	}

	depLogStreamsMu.RLock()
	b, exists := depLogStreams[uint(id)]
	depLogStreamsMu.RUnlock()

	if !exists {
		fmt.Fprintf(c.Writer, "event: done\ndata: %s\n\n", dep.Status)
		c.Writer.Flush()
		return
	}

	sub := b.subscribe()
	defer b.unsubscribe(sub)

	ctx := c.Request.Context()
	for {
		select {
		case line, ok := <-sub:
			if !ok {
				fmt.Fprintf(c.Writer, "event: done\ndata: closed\n\n")
				c.Writer.Flush()
				return
			}
			if line == "\x00DONE" {
				var latest model.Dependency
				database.DB.First(&latest, id)
				fmt.Fprintf(c.Writer, "event: done\ndata: %s\n\n", latest.Status)
				c.Writer.Flush()
				return
			}
			fmt.Fprintf(c.Writer, "data: %s\n\n", line)
			c.Writer.Flush()
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Minute):
			fmt.Fprintf(c.Writer, "event: done\ndata: timeout\n\n")
			c.Writer.Flush()
			return
		}
	}
}

func (h *DepsHandler) Reinstall(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var dep model.Dependency
	if err := database.DB.First(&dep, id).Error; err != nil {
		response.NotFound(c, "依赖不存在")
		return
	}

	if dep.Status == model.DepStatusInstalling || dep.Status == model.DepStatusRemoving {
		response.BadRequest(c, "依赖正在处理中")
		return
	}

	database.DB.Model(&dep).Updates(map[string]interface{}{
		"status": model.DepStatusInstalling,
		"log":    "",
	})

	go installDependency(dep.ID, dep.Type, dep.Name)

	response.Success(c, gin.H{"message": "重新安装中"})
}

func (h *DepsHandler) PipList(c *gin.Context) {
	out, err := exec.Command("pip3", "list", "--format=json").Output()
	if err != nil {
		out, err = exec.Command("pip", "list", "--format=json").Output()
		if err != nil {
			response.InternalError(c, "pip 不可用")
			return
		}
	}
	c.Data(200, "application/json", out)
}

func (h *DepsHandler) NpmList(c *gin.Context) {
	out, err := exec.Command("npm", "list", "-g", "--json", "--depth=0").Output()
	if err != nil {
		response.InternalError(c, "npm 不可用")
		return
	}
	c.Data(200, "application/json", out)
}

func (h *DepsHandler) GetMirrors(c *gin.Context) {
	result := gin.H{
		"pip_mirror":   "",
		"npm_mirror":   "",
		"linux_mirror": "",
	}

	if out, err := exec.Command("pip3", "config", "get", "global.index-url").Output(); err == nil {
		result["pip_mirror"] = strings.TrimSpace(string(out))
	} else if out, err := exec.Command("pip", "config", "get", "global.index-url").Output(); err == nil {
		result["pip_mirror"] = strings.TrimSpace(string(out))
	}

	if out, err := exec.Command("npm", "config", "get", "registry").Output(); err == nil {
		val := strings.TrimSpace(string(out))
		if val != "https://registry.npmjs.org/" {
			result["npm_mirror"] = val
		}
	}

	if data, err := os.ReadFile("/etc/apk/repositories"); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if line != "" && !strings.HasPrefix(line, "#") {
				parts := strings.SplitN(line, "/v", 2)
				if len(parts) > 0 {
					result["linux_mirror"] = strings.TrimRight(parts[0], "/")
					break
				}
			}
		}
	}

	response.Success(c, result)
}

func (h *DepsHandler) SetMirrors(c *gin.Context) {
	var req struct {
		PipMirror   *string `json:"pip_mirror"`
		NpmMirror   *string `json:"npm_mirror"`
		LinuxMirror *string `json:"linux_mirror"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "请求参数错误")
		return
	}

	var errors []string

	if req.PipMirror != nil {
		mirror := strings.TrimSpace(*req.PipMirror)
		if mirror == "" {
			if out, err := exec.Command("pip3", "config", "unset", "global.index-url").CombinedOutput(); err != nil {
				exec.Command("pip", "config", "unset", "global.index-url").CombinedOutput()
				_ = out
			}
		} else {
			if !strings.HasPrefix(mirror, "http://") && !strings.HasPrefix(mirror, "https://") {
				errors = append(errors, "pip 镜像源必须以 http:// 或 https:// 开头")
			} else {
				if out, err := exec.Command("pip3", "config", "set", "global.index-url", mirror).CombinedOutput(); err != nil {
					if out2, err2 := exec.Command("pip", "config", "set", "global.index-url", mirror).CombinedOutput(); err2 != nil {
						errors = append(errors, "设置 pip 镜像源失败: "+string(out)+string(out2))
					}
				}
				host := extractHost(mirror)
				if host != "" {
					exec.Command("pip3", "config", "set", "global.trusted-host", host).Run()
				}
			}
		}
	}

	if req.NpmMirror != nil {
		mirror := strings.TrimSpace(*req.NpmMirror)
		if mirror == "" {
			exec.Command("npm", "config", "set", "registry", "https://registry.npmjs.org/").Run()
		} else {
			if !strings.HasPrefix(mirror, "http://") && !strings.HasPrefix(mirror, "https://") {
				errors = append(errors, "npm 镜像源必须以 http:// 或 https:// 开头")
			} else {
				if out, err := exec.Command("npm", "config", "set", "registry", mirror).CombinedOutput(); err != nil {
					errors = append(errors, "设置 npm 镜像源失败: "+string(out))
				}
			}
		}
	}

	if req.LinuxMirror != nil {
		mirror := strings.TrimSpace(*req.LinuxMirror)
		if mirror == "" {
			mirror = "https://dl-cdn.alpinelinux.org/alpine"
		}
		if !strings.HasPrefix(mirror, "http://") && !strings.HasPrefix(mirror, "https://") {
			errors = append(errors, "Linux 镜像源必须以 http:// 或 https:// 开头")
		} else {
			mirror = strings.TrimRight(mirror, "/")
			out, err := exec.Command("cat", "/etc/alpine-release").Output()
			ver := "3.19"
			if err == nil {
				parts := strings.Split(strings.TrimSpace(string(out)), ".")
				if len(parts) >= 2 {
					ver = parts[0] + "." + parts[1]
				}
			}
			content := fmt.Sprintf("%s/v%s/main\n%s/v%s/community\n", mirror, ver, mirror, ver)
			if err := os.WriteFile("/etc/apk/repositories", []byte(content), 0644); err != nil {
				errors = append(errors, "设置 Linux 镜像源失败: "+err.Error())
			}
		}
	}

	if len(errors) > 0 {
		response.BadRequest(c, strings.Join(errors, "; "))
		return
	}

	response.Success(c, gin.H{"message": "镜像源设置成功"})
}

func extractHost(url string) string {
	url = strings.TrimPrefix(url, "https://")
	url = strings.TrimPrefix(url, "http://")
	parts := strings.SplitN(url, "/", 2)
	if len(parts) > 0 {
		hostPort := strings.SplitN(parts[0], ":", 2)
		return hostPort[0]
	}
	return ""
}

func runCmdWithSSE(cmd *exec.Cmd, id uint, successStatus string, deleteOnSuccess bool) {
	broadcaster := getOrCreateBroadcaster(id)
	defer removeBroadcaster(id)

	pipe, err := cmd.StdoutPipe()
	if err != nil {
		database.DB.Model(&model.Dependency{}).Where("id = ?", id).Updates(map[string]interface{}{
			"status": model.DepStatusFailed,
			"log":    err.Error(),
		})
		broadcaster.done()
		return
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		database.DB.Model(&model.Dependency{}).Where("id = ?", id).Updates(map[string]interface{}{
			"status": model.DepStatusFailed,
			"log":    err.Error(),
		})
		broadcaster.done()
		return
	}

	var logBuf strings.Builder
	scanner := bufio.NewScanner(pipe)
	scanner.Buffer(make([]byte, 64*1024), 256*1024)
	for scanner.Scan() {
		line := scanner.Text()
		logBuf.WriteString(line)
		logBuf.WriteString("\n")
		broadcaster.broadcast(line)
		database.DB.Model(&model.Dependency{}).Where("id = ?", id).Update("log", logBuf.String())
	}

	status := successStatus
	if err := cmd.Wait(); err != nil {
		status = model.DepStatusFailed
	}

	if deleteOnSuccess && status == successStatus {
		database.DB.Delete(&model.Dependency{}, id)
	} else {
		database.DB.Model(&model.Dependency{}).Where("id = ?", id).Updates(map[string]interface{}{
			"status": status,
			"log":    logBuf.String(),
		})
	}

	broadcaster.done()
}

func ensureTmpDir() {
	os.MkdirAll("/tmp", 0o1777)
}

func installDependency(id uint, depType, name string) {
	ensureTmpDir()
	var cmd *exec.Cmd
	depsDir := filepath.Join(config.C.Data.Dir, "deps")
	switch depType {
	case model.DepTypeNodeJS:
		cmd = exec.Command("npm", "install", "--prefix", filepath.Join(depsDir, "nodejs"), name)
	case model.DepTypePython:
		pipBin := filepath.Join(depsDir, "python", "venv", "bin", "pip")
		cmd = exec.Command(pipBin, "install", name)
		cmd.Env = append(os.Environ(), "TMPDIR=/tmp")
	case model.DepTypeLinux:
		cmd = exec.Command("bash", "-c", "apt-get install -y "+name+" 2>&1 || yum install -y "+name+" 2>&1 || apk add "+name+" 2>&1")
	default:
		database.DB.Model(&model.Dependency{}).Where("id = ?", id).Updates(map[string]interface{}{
			"status": model.DepStatusFailed,
			"log":    "不支持的类型",
		})
		return
	}

	runCmdWithSSE(cmd, id, model.DepStatusInstalled, false)
}

func uninstallDependency(id uint, depType, name string) {
	var cmd *exec.Cmd
	depsDir := filepath.Join(config.C.Data.Dir, "deps")
	switch depType {
	case model.DepTypeNodeJS:
		cmd = exec.Command("npm", "uninstall", "--prefix", filepath.Join(depsDir, "nodejs"), name)
	case model.DepTypePython:
		pipBin := filepath.Join(depsDir, "python", "venv", "bin", "pip")
		cmd = exec.Command(pipBin, "uninstall", "-y", name)
	case model.DepTypeLinux:
		cmd = exec.Command("bash", "-c", "apt-get remove -y "+name+" 2>&1 || yum remove -y "+name+" 2>&1 || apk del "+name+" 2>&1")
	default:
		database.DB.Delete(&model.Dependency{}, id)
		return
	}

	runCmdWithSSE(cmd, id, model.DepStatusInstalled, true)
}

func forceUninstallDependency(depType, name string) {
	depsDir := filepath.Join(config.C.Data.Dir, "deps")
	var cmd *exec.Cmd
	switch depType {
	case model.DepTypeNodeJS:
		cmd = exec.Command("npm", "uninstall", "--prefix", filepath.Join(depsDir, "nodejs"), "--force", name)
	case model.DepTypePython:
		pipBin := filepath.Join(depsDir, "python", "venv", "bin", "pip")
		cmd = exec.Command(pipBin, "uninstall", "-y", "--no-deps", name)
	case model.DepTypeLinux:
		cmd = exec.Command("bash", "-c", "apt-get remove --force-yes -y "+name+" 2>&1 || yum remove -y "+name+" 2>&1 || apk del --force-broken-world "+name+" 2>&1")
	default:
		return
	}
	cmd.CombinedOutput()
}

func (h *DepsHandler) RegisterRoutes(r *gin.RouterGroup) {
	deps := r.Group("/deps", middleware.JWTAuth(), middleware.RequireAdmin())
	{
		deps.GET("", h.List)
		deps.POST("", h.Create)
		deps.POST("/batch-delete", h.BatchDelete)
		deps.DELETE("/:id", h.Delete)
		deps.GET("/:id/status", h.GetStatus)
		deps.GET("/:id/log-stream", h.LogStream)
		deps.PUT("/:id/reinstall", h.Reinstall)

		deps.GET("/pip", h.PipList)
		deps.GET("/npm", h.NpmList)

		deps.GET("/mirrors", h.GetMirrors)
		deps.PUT("/mirrors", h.SetMirrors)
	}
}

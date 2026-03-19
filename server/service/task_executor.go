package service

import (
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/model"
)

type TaskExecutor struct {
	scriptsDir       string
	logDir           string
	runningProcesses map[uint]*os.Process
	processLock      sync.Mutex
}

func NewTaskExecutor() *TaskExecutor {
	return &TaskExecutor{
		scriptsDir:       config.C.Data.ScriptsDir,
		logDir:           config.C.Data.LogDir,
		runningProcesses: make(map[uint]*os.Process),
	}
}

func (e *TaskExecutor) OnTaskScheduled(req *ExecutionRequest) {
	log.Printf("task %d scheduled: %s", req.TaskID, req.Task.Name)
}

func (e *TaskExecutor) OnTaskExecuting(req *ExecutionRequest) error {
	task := req.Task

	if task.DependsOn != nil {
		var depTask model.Task
		if err := database.DB.First(&depTask, *task.DependsOn).Error; err == nil {
			if depTask.LastRunStatus == nil || *depTask.LastRunStatus != model.RunSuccess {
				return fmt.Errorf("依赖任务 '%s' 上次执行未成功", depTask.Name)
			}
		}
	}

	randomDelay := model.GetConfigInt("random_delay", 0)
	if randomDelay > 0 {
		delay := rand.Intn(randomDelay) + 1
		time.Sleep(time.Duration(delay) * time.Second)
	}

	now := time.Now()
	database.DB.Model(task).Updates(map[string]interface{}{
		"status":      model.TaskStatusRunning,
		"last_run_at": now,
	})

	logID := fmt.Sprintf("%d_%d", task.ID, now.UnixNano())
	tinyLog, err := GetTinyLogManager().Create(logID)
	if err != nil {
		return fmt.Errorf("failed to create log: %w", err)
	}

	relLogPath := GetRelativeLogPath(task.ID)
	runningStatus := model.LogStatusRunning
	taskLog := &model.TaskLog{
		TaskID:    task.ID,
		Status:    &runningStatus,
		StartedAt: now,
		LogPath:   &relLogPath,
	}
	database.DB.Create(taskLog)

	req.LogID = logID
	req.TaskLogID = taskLog.ID

	go e.runTask(req, taskLog, tinyLog)

	return nil
}

func (e *TaskExecutor) OnTaskStarted(req *ExecutionRequest) {
	log.Printf("task %d started: %s", req.TaskID, req.Task.Name)
}

func (e *TaskExecutor) OnTaskCompleted(req *ExecutionRequest, result *ExecutionResult) {
	log.Printf("task %d completed: success=%v, duration=%.2fs",
		req.TaskID, result.Success, result.Duration)
}

func (e *TaskExecutor) OnTaskFailed(req *ExecutionRequest, err error) {
	log.Printf("task %d failed: %v", req.TaskID, err)

	task := req.Task
	database.DB.Model(task).Updates(map[string]interface{}{
		"status": model.TaskStatusEnabled,
	})
}

func KillProcessGroup(p *os.Process) {
	if p == nil {
		return
	}
	killGroup(p)
	p.Kill()
}

func KillProcessByPid(pid int) {
	killGroupByPid(pid)
	p, err := os.FindProcess(pid)
	if err != nil {
		return
	}
	p.Kill()
}

func (e *TaskExecutor) StopTask(taskID uint) bool {
	e.processLock.Lock()
	defer e.processLock.Unlock()

	if p, ok := e.runningProcesses[taskID]; ok {
		KillProcessGroup(p)
		delete(e.runningProcesses, taskID)
		return true
	}
	return false
}

func (e *TaskExecutor) runTask(req *ExecutionRequest, taskLog *model.TaskLog, tinyLog *TinyLog) {
	task := req.Task
	startTime := time.Now()
	exitCode := 0
	success := false

	var envVarRecords []model.EnvVar
	database.DB.Where("enabled = ?", true).Find(&envVarRecords)
	envVars := make(map[string]string)
	for _, ev := range envVarRecords {
		if existing, ok := envVars[ev.Name]; ok {
			envVars[ev.Name] = existing + "&" + ev.Value
		} else {
			envVars[ev.Name] = ev.Value
		}
	}

	depsDir := filepath.Join(config.C.Data.Dir, "deps")
	nodeBin := filepath.Join(depsDir, "nodejs", "node_modules", ".bin")
	nodeModules := filepath.Join(depsDir, "nodejs", "node_modules")
	venvBin := filepath.Join(depsDir, "python", "venv", "bin")

	envVars["NODE_PATH"] = nodeModules
	if currentPath := os.Getenv("PATH"); currentPath != "" {
		envVars["PATH"] = strings.Join([]string{nodeBin, venvBin, currentPath}, string(os.PathListSeparator))
	} else {
		envVars["PATH"] = strings.Join([]string{nodeBin, venvBin}, string(os.PathListSeparator))
	}

	venvLib := filepath.Join(depsDir, "python", "venv", "lib")
	if entries, err := os.ReadDir(venvLib); err == nil {
		for _, entry := range entries {
			if entry.IsDir() && strings.HasPrefix(entry.Name(), "python") {
				envVars["PYTHONPATH"] = filepath.Join(venvLib, entry.Name(), "site-packages")
				break
			}
		}
	}

	commandTimeout := model.GetConfigInt("command_timeout", 86400)
	maxLogSize := model.GetConfigInt("max_log_content_size", 102400)

	timeout := task.Timeout
	if timeout <= 0 {
		timeout = commandTimeout
	}

	defer func() {
		if r := recover(); r != nil {
			log.Printf("task %d panicked: %v", req.TaskID, r)
			fmt.Fprintf(tinyLog, "\n[任务异常崩溃: %v]\n", r)
			exitCode = 1
		}

		duration := time.Since(startTime).Seconds()

		compressed, _ := tinyLog.Close()
		GetTinyLogManager().Remove(tinyLog.LogID)

		logStatus := model.LogStatusSuccess
		if exitCode != 0 {
			logStatus = model.LogStatusFailed
		}

		endedAt := time.Now()
		database.DB.Model(taskLog).Updates(map[string]interface{}{
			"status":   logStatus,
			"content":  compressed,
			"ended_at": endedAt,
			"duration": duration,
		})

		runStatus := model.RunSuccess
		if !success {
			runStatus = model.RunFailed
		}

		database.DB.Model(task).Updates(map[string]interface{}{
			"status":            model.TaskStatusEnabled,
			"last_run_status":   runStatus,
			"last_running_time": duration,
			"pid":               nil,
		})

		e.processLock.Lock()
		delete(e.runningProcesses, req.TaskID)
		e.processLock.Unlock()

		result := &ExecutionResult{
			Success:  success,
			ExitCode: exitCode,
			Duration: duration,
		}
		e.OnTaskCompleted(req, result)
	}()

	logMgr := GetLogStreamManager()
	var fullLogPath string
	if taskLog.LogPath != nil {
		fullLogPath = filepath.Join(e.logDir, *taskLog.LogPath)
	}
	defer func() {
		if fullLogPath != "" {
			logMgr.CloseStream(fullLogPath)
		}
	}()

	onOutput := func(line string) {
		fmt.Fprintf(tinyLog, "%s\n", line)
		if fullLogPath != "" {
			logMgr.Write(fullLogPath, line+"\n")
		}
	}

	var outputCollector strings.Builder

	onOutputWithCollect := func(line string) {
		onOutput(line)
		outputCollector.WriteString(line + "\n")
	}

	onOutput(fmt.Sprintf("=== 开始执行 [%s] ===", startTime.Format("2006-01-02 15:04:05")))

	if task.TaskBefore != nil && *task.TaskBefore != "" {
		onOutput("[执行前置脚本]")
		RunInlineScript(*task.TaskBefore, e.scriptsDir, envVars, 60, onOutput)
	}

	RunHookScript("task_before.sh", e.scriptsDir, envVars, onOutput)

	retries := 0
	var lastExitCode int
	depInstalled := false

	for retries <= task.MaxRetries {
		if retries > 0 {
			onOutput(fmt.Sprintf("[第 %d 次重试，等待 %d 秒]", retries, task.RetryInterval))
			time.Sleep(time.Duration(task.RetryInterval) * time.Second)
		}

		outputCollector.Reset()
		result, process, err := RunCommand(task.Command, e.scriptsDir, timeout, envVars, maxLogSize, onOutputWithCollect)
		if err != nil {
			onOutput(fmt.Sprintf("[执行错误: %s]", err.Error()))
			retries++
			lastExitCode = 1
			continue
		}

		if process != nil {
			e.processLock.Lock()
			e.runningProcesses[req.TaskID] = process
			pid := process.Pid
			e.processLock.Unlock()
			database.DB.Model(task).Update("pid", pid)
		}

		lastExitCode = result.ReturnCode
		if result.ReturnCode == 0 {
			success = true
			break
		}

		if !depInstalled && model.GetConfigInt("auto_install_deps", 1) == 1 {
			collected := outputCollector.String()
			if e.detectAndInstallDeps(collected, envVars, onOutput) {
				depInstalled = true
				onOutput("[依赖已安装，自动重试执行]")
				continue
			}
		}

		retries++
	}

	exitCode = lastExitCode

	if task.TaskAfter != nil && *task.TaskAfter != "" {
		onOutput("[执行后置脚本]")
		RunInlineScript(*task.TaskAfter, e.scriptsDir, envVars, 60, onOutput)
	}

	RunHookScript("task_after.sh", e.scriptsDir, envVars, onOutput)
	RunHookScript("extra.sh", e.scriptsDir, envVars, onOutput)

	endTime := time.Now()
	duration := endTime.Sub(startTime).Seconds()

	onOutput(fmt.Sprintf("=== 执行结束 [%s] 耗时 %.2f 秒 退出码 %d ===",
		endTime.Format("2006-01-02 15:04:05"), duration, lastExitCode))
}

var (
	pyModuleRe  = regexp.MustCompile(`(?:ModuleNotFoundError|ImportError):\s*No module named\s+'([^']+)'`)
	nodeModuleRe = regexp.MustCompile(`(?:Cannot find module|Error \[ERR_MODULE_NOT_FOUND\].*)'([^']+)'`)
)

func (e *TaskExecutor) detectAndInstallDeps(output string, envVars map[string]string, onOutput OnOutputFunc) bool {
	installed := false

	depsDir := filepath.Join(config.C.Data.Dir, "deps")

	if matches := pyModuleRe.FindStringSubmatch(output); len(matches) > 1 {
		modName := strings.Split(matches[1], ".")[0]
		onOutput(fmt.Sprintf("[自动安装 Python 依赖: %s]", modName))
		venvPip := filepath.Join(depsDir, "python", "venv", "bin", "pip3")
		if _, err := os.Stat(venvPip); err != nil {
			venvPip = "pip3"
		}
		cmd := exec.Command(venvPip, "install", modName)
		cmd.Env = buildEnvSlice(envVars)
		out, err := cmd.CombinedOutput()
		if err != nil {
			onOutput(fmt.Sprintf("[安装失败: %s]", strings.TrimSpace(string(out))))
		} else {
			onOutput(fmt.Sprintf("[安装成功: %s]", modName))
			installed = true
		}
	}

	if matches := nodeModuleRe.FindStringSubmatch(output); len(matches) > 1 {
		modName := matches[1]
		if strings.HasPrefix(modName, ".") || strings.HasPrefix(modName, "/") {
			return installed
		}
		onOutput(fmt.Sprintf("[自动安装 Node.js 依赖: %s]", modName))
		nodeDir := filepath.Join(depsDir, "nodejs")
		os.MkdirAll(nodeDir, 0755)
		cmd := exec.Command("npm", "install", modName, "--prefix", nodeDir)
		cmd.Env = buildEnvSlice(envVars)
		out, err := cmd.CombinedOutput()
		if err != nil {
			onOutput(fmt.Sprintf("[安装失败: %s]", strings.TrimSpace(string(out))))
		} else {
			onOutput(fmt.Sprintf("[安装成功: %s]", modName))
			installed = true
		}
	}

	return installed
}

func buildEnvSlice(envVars map[string]string) []string {
	env := os.Environ()
	for k, v := range envVars {
		env = append(env, k+"="+v)
	}
	return env
}

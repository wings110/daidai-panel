package service

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/model"
	"daidai-panel/pkg/cron"
)

type PullCallback func(line string)

func PullSubscription(sub *model.Subscription) (string, error) {
	return PullSubscriptionWithCallback(sub, nil)
}

func PullSubscriptionWithCallback(sub *model.Subscription, onOutput PullCallback) (string, error) {
	startTime := time.Now()

	var sshKeyPath string
	if sub.SSHKeyID != nil {
		var sshKey model.SSHKey
		if err := database.DB.First(&sshKey, *sub.SSHKeyID).Error; err == nil {
			tmpFile, err := writeTempSSHKey(sshKey.PrivateKey)
			if err != nil {
				return "", fmt.Errorf("写入 SSH 密钥失败: %w", err)
			}
			defer os.Remove(tmpFile)
			sshKeyPath = tmpFile
		}
	}

	var fullLog strings.Builder
	emit := func(line string) {
		fullLog.WriteString(line)
		fullLog.WriteString("\n")
		if onOutput != nil {
			onOutput(line)
		}
	}

	emit(fmt.Sprintf("[开始拉取] %s (%s)", sub.Name, sub.Type))

	var output string
	var pullErr error

	switch sub.Type {
	case model.SubTypeSingleFile:
		output, pullErr = pullSingleFileWithCallback(sub, sshKeyPath, emit)
	default:
		output, pullErr = pullGitRepoWithCallback(sub, sshKeyPath, emit)
	}

	duration := time.Since(startTime).Seconds()

	status := 0
	if pullErr != nil {
		status = 1
		emit(fmt.Sprintf("[错误] %s", pullErr.Error()))
	}

	emit(fmt.Sprintf("[完成] 耗时 %.2f 秒, 状态: %s", duration, map[int]string{0: "成功", 1: "失败"}[status]))

	if status == 0 && sub.AutoAddTask {
		autoCreateTasksFromScripts(sub, emit)
	}

	subLog := model.SubLog{
		SubscriptionID: sub.ID,
		Status:         status,
		Content:        fullLog.String(),
		Duration:       duration,
	}
	database.DB.Create(&subLog)

	now := time.Now()
	database.DB.Model(sub).Updates(map[string]interface{}{
		"last_pull_at": &now,
		"status":       status,
	})

	return output, pullErr
}

func runCmdWithCallback(cmd *exec.Cmd, emit PullCallback) (string, error) {
	pipe, err := cmd.StdoutPipe()
	if err != nil {
		return "", err
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		return "", err
	}

	var buf strings.Builder
	scanner := bufio.NewScanner(pipe)
	scanner.Buffer(make([]byte, 64*1024), 256*1024)
	for scanner.Scan() {
		line := scanner.Text()
		buf.WriteString(line)
		buf.WriteString("\n")
		emit(line)
	}

	err = cmd.Wait()
	return buf.String(), err
}

func pullGitRepoWithCallback(sub *model.Subscription, sshKeyPath string, emit PullCallback) (string, error) {
	saveDir := sub.SaveDir
	if saveDir == "" {
		saveDir = sub.Alias
		if saveDir == "" {
			parts := strings.Split(sub.URL, "/")
			saveDir = strings.TrimSuffix(parts[len(parts)-1], ".git")
		}
	}

	destDir := filepath.Join(config.C.Data.ScriptsDir, saveDir)

	env := os.Environ()
	if sshKeyPath != "" {
		sshCmd := fmt.Sprintf("ssh -i %s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null", sshKeyPath)
		env = append(env, "GIT_SSH_COMMAND="+sshCmd)
	}

	if IsGitRepo(destDir) {
		emit("[git reset --hard]")
		GitReset(destDir)

		emit("[git pull]")
		cmd := exec.Command("git", "pull")
		cmd.Dir = destDir
		cmd.Env = env
		return runCmdWithCallback(cmd, emit)
	}

	emit(fmt.Sprintf("[git clone] %s -> %s", sub.URL, saveDir))
	os.MkdirAll(destDir, 0755)
	args := []string{"clone", "--depth", "1"}
	if sub.Branch != "" {
		args = append(args, "-b", sub.Branch)
	}
	args = append(args, sub.URL, destDir)
	cmd := exec.Command("git", args...)
	cmd.Dir = config.C.Data.ScriptsDir
	cmd.Env = env
	return runCmdWithCallback(cmd, emit)
}

func pullSingleFileWithCallback(sub *model.Subscription, _ string, emit PullCallback) (string, error) {
	saveDir := sub.SaveDir
	if saveDir == "" {
		saveDir = "downloads"
	}

	parts := strings.Split(sub.URL, "/")
	filename := parts[len(parts)-1]
	if sub.Alias != "" {
		filename = sub.Alias
	}

	destPath := filepath.Join(config.C.Data.ScriptsDir, saveDir, filename)
	emit(fmt.Sprintf("[下载] %s -> %s/%s", sub.URL, saveDir, filename))
	output, err := DownloadFile(sub.URL, destPath)
	if output != "" {
		emit(output)
	}
	return output, err
}

func writeTempSSHKey(privateKey string) (string, error) {
	tmpFile, err := os.CreateTemp("", "ssh_key_*")
	if err != nil {
		return "", err
	}
	defer tmpFile.Close()

	if _, err := tmpFile.WriteString(privateKey); err != nil {
		os.Remove(tmpFile.Name())
		return "", err
	}

	os.Chmod(tmpFile.Name(), 0600)
	return tmpFile.Name(), nil
}

var cronCommentRe = regexp.MustCompile(`(?i)#\s*cron\s*[:：]\s*(.+)`)

func autoCreateTasksFromScripts(sub *model.Subscription, emit PullCallback) {
	saveDir := sub.SaveDir
	if saveDir == "" {
		saveDir = sub.Alias
		if saveDir == "" {
			parts := strings.Split(sub.URL, "/")
			saveDir = strings.TrimSuffix(parts[len(parts)-1], ".git")
		}
	}

	scriptsDir := filepath.Join(config.C.Data.ScriptsDir, saveDir)
	scriptExts := map[string]bool{".js": true, ".ts": true, ".py": true, ".sh": true}
	created := 0

	filepath.Walk(scriptsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(info.Name()))
		if !scriptExts[ext] {
			return nil
		}

		if sub.Whitelist != "" {
			matched := false
			for _, pattern := range strings.Split(sub.Whitelist, ",") {
				pattern = strings.TrimSpace(pattern)
				if pattern != "" && strings.Contains(info.Name(), pattern) {
					matched = true
					break
				}
			}
			if !matched {
				return nil
			}
		}
		if sub.Blacklist != "" {
			for _, pattern := range strings.Split(sub.Blacklist, ",") {
				pattern = strings.TrimSpace(pattern)
				if pattern != "" && strings.Contains(info.Name(), pattern) {
					return nil
				}
			}
		}

		cronExpr := extractCronFromFile(path)
		if cronExpr == "" {
			return nil
		}

		relPath, _ := filepath.Rel(config.C.Data.ScriptsDir, path)
		taskName := strings.TrimSuffix(info.Name(), ext)

		var existing model.Task
		if database.DB.Where("command LIKE ?", "%"+relPath+"%").First(&existing).Error == nil {
			return nil
		}

		task := model.Task{
			Name:            taskName,
			Command:         "task " + relPath,
			CronExpression:  cronExpr,
			Status:          model.TaskStatusEnabled,
			Timeout:         86400,
			NotifyOnFailure: true,
		}
		if database.DB.Create(&task).Error == nil {
			GetSchedulerV2().AddJob(&task)
			created++
			emit(fmt.Sprintf("[自动添加任务] %s (cron: %s)", taskName, cronExpr))
		}
		return nil
	})

	if created > 0 {
		emit(fmt.Sprintf("[共自动添加 %d 个定时任务]", created))
	}
}

func extractCronFromFile(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	lineCount := 0
	for scanner.Scan() {
		lineCount++
		if lineCount > 50 {
			break
		}
		line := scanner.Text()
		matches := cronCommentRe.FindStringSubmatch(line)
		if len(matches) > 1 {
			expr := strings.TrimSpace(matches[1])
			result := cron.Parse(expr)
			if result.Valid {
				return expr
			}
		}
	}
	return ""
}

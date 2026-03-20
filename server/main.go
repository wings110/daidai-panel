package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/model"
	"daidai-panel/router"
	"daidai-panel/service"

	"github.com/gin-gonic/gin"
)

func main() {
	cfg, err := config.Load("config.yaml")
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	database.Init(&cfg.Database)

	database.AutoMigrate(
		&model.User{},
		&model.TokenBlocklist{},
		&model.Task{},
		&model.TaskLog{},
		&model.SystemConfig{},
		&model.EnvVar{},
		&model.ScriptVersion{},
		&model.Subscription{},
		&model.SubLog{},
		&model.NotifyChannel{},
		&model.SSHKey{},
		&model.LoginLog{},
		&model.LoginAttempt{},
		&model.UserSession{},
		&model.IPWhitelist{},
		&model.SecurityAudit{},
		&model.TwoFactorAuth{},
		&model.OpenApp{},
		&model.ApiCallLog{},
		&model.Platform{},
		&model.PlatformToken{},
		&model.PlatformTokenLog{},
		&model.Dependency{},
	)

	database.EnsureColumns()

	model.InitDefaultConfigs()

	verifyInstalledDeps()

	service.InitSchedulerV2()
	defer service.ShutdownSchedulerV2()

	service.StartResourceWatcher()
	defer service.StopResourceWatcher()

	if cfg.Server.Mode == "release" {
		gin.SetMode(gin.ReleaseMode)
	}

	engine := gin.New()
	engine.SetTrustedProxies([]string{"127.0.0.1", "::1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"})
	engine.RemoteIPHeaders = []string{"X-Real-IP", "X-Forwarded-For"}
	engine.Use(gin.Logger())
	engine.Use(gin.Recovery())

	router.Setup(engine)

	addr := fmt.Sprintf(":%d", cfg.Server.Port)
	log.Printf("server starting on %s", addr)
	if err := engine.Run(addr); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}

func verifyInstalledDeps() {
	var deps []model.Dependency
	database.DB.Where("status = ?", model.DepStatusInstalled).Find(&deps)
	if len(deps) == 0 {
		return
	}

	depsDir := filepath.Join(config.C.Data.Dir, "deps")
	resetCount := 0

	for _, dep := range deps {
		exists := false
		switch dep.Type {
		case model.DepTypeNodeJS:
			modDir := filepath.Join(depsDir, "nodejs", "node_modules", dep.Name)
			if _, err := os.Stat(modDir); err == nil {
				exists = true
			}
		case model.DepTypePython:
			venvPip := filepath.Join(depsDir, "python", "venv", "bin", "pip")
			if _, err := os.Stat(venvPip); err == nil {
				out, err := exec.Command(venvPip, "show", dep.Name).CombinedOutput()
				if err == nil && strings.Contains(string(out), "Name:") {
					exists = true
				}
			}
		case model.DepTypeLinux:
			if out, err := exec.Command("which", dep.Name).CombinedOutput(); err == nil && len(strings.TrimSpace(string(out))) > 0 {
				exists = true
			} else if exec.Command("apk", "info", "-e", dep.Name).Run() == nil {
				exists = true
			}
		}

		if !exists {
			database.DB.Model(&dep).Updates(map[string]interface{}{
				"status": model.DepStatusFailed,
				"log":    dep.Log + "\n[启动校验] 依赖未检测到，可能因容器重建而丢失，请重新安装",
			})
			resetCount++
			log.Printf("dep verify: %s/%s not found, status reset to failed", dep.Type, dep.Name)
		}
	}

	if resetCount > 0 {
		log.Printf("dep verify: %d dependencies reset to failed (not found on system)", resetCount)
	}

	var stale []model.Dependency
	database.DB.Where("status IN ?", []string{model.DepStatusInstalling, model.DepStatusRemoving}).Find(&stale)
	for _, dep := range stale {
		database.DB.Model(&dep).Updates(map[string]interface{}{
			"status": model.DepStatusFailed,
			"log":    dep.Log + "\n[启动校验] 操作因服务重启而中断",
		})
		log.Printf("dep verify: %s/%s was %s, reset to failed", dep.Type, dep.Name, dep.Status)
	}
}

package service

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"daidai-panel/config"
	"daidai-panel/database"
	"daidai-panel/model"
)

type ScriptFile struct {
	Path    string `json:"path"`
	Content string `json:"content"`
}

type BackupData struct {
	Version   string                `json:"version"`
	CreatedAt time.Time             `json:"created_at"`
	Tasks     []model.Task          `json:"tasks"`
	EnvVars   []model.EnvVar        `json:"env_vars"`
	Subs      []model.Subscription  `json:"subscriptions"`
	Channels  []model.NotifyChannel `json:"notify_channels"`
	SSHKeys   []model.SSHKey        `json:"ssh_keys"`
	Configs   []model.SystemConfig  `json:"system_configs"`
	Scripts   []ScriptFile          `json:"scripts,omitempty"`
	Deps      []model.Dependency    `json:"dependencies,omitempty"`
}

func collectScripts(scriptsDir string) []ScriptFile {
	var files []ScriptFile
	allowedExts := map[string]bool{".js": true, ".py": true, ".ts": true, ".sh": true}

	filepath.Walk(scriptsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(info.Name()))
		if !allowedExts[ext] {
			return nil
		}
		if info.Size() > 10*1024*1024 {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return nil
		}
		rel, _ := filepath.Rel(scriptsDir, path)
		rel = filepath.ToSlash(rel)
		files = append(files, ScriptFile{
			Path:    rel,
			Content: base64.StdEncoding.EncodeToString(data),
		})
		return nil
	})
	return files
}

func restoreScripts(scriptsDir string, scripts []ScriptFile) {
	for _, sf := range scripts {
		if strings.Contains(sf.Path, "..") {
			continue
		}
		data, err := base64.StdEncoding.DecodeString(sf.Content)
		if err != nil {
			continue
		}
		fullPath := filepath.Join(scriptsDir, filepath.FromSlash(sf.Path))
		os.MkdirAll(filepath.Dir(fullPath), 0755)
		os.WriteFile(fullPath, data, 0755)
	}
}

func CreateBackup(password string) (string, error) {
	var data BackupData
	data.Version = "0.3.0"
	data.CreatedAt = time.Now()

	database.DB.Find(&data.Tasks)
	database.DB.Find(&data.EnvVars)
	database.DB.Find(&data.Subs)
	database.DB.Find(&data.Channels)
	database.DB.Find(&data.SSHKeys)
	database.DB.Find(&data.Configs)
	database.DB.Find(&data.Deps)
	data.Scripts = collectScripts(config.C.Data.ScriptsDir)

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to marshal backup: %w", err)
	}

	backupDir := filepath.Join(config.C.Data.Dir, "backups")
	os.MkdirAll(backupDir, 0755)

	var filename string
	var finalData []byte

	if password != "" {
		encrypted, err := encryptData(jsonData, password)
		if err != nil {
			return "", fmt.Errorf("failed to encrypt backup: %w", err)
		}
		finalData = encrypted
		filename = fmt.Sprintf("backup_%s.enc", time.Now().Format("20060102_150405"))
	} else {
		finalData = jsonData
		filename = fmt.Sprintf("backup_%s.json", time.Now().Format("20060102_150405"))
	}

	filePath := filepath.Join(backupDir, filename)

	if err := os.WriteFile(filePath, finalData, 0644); err != nil {
		return "", fmt.Errorf("failed to write backup: %w", err)
	}

	return filePath, nil
}

func encryptData(data []byte, password string) ([]byte, error) {
	key := sha256.Sum256([]byte(password))
	block, err := aes.NewCipher(key[:])
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}

	return gcm.Seal(nonce, nonce, data, nil), nil
}

func decryptData(data []byte, password string) ([]byte, error) {
	key := sha256.Sum256([]byte(password))
	block, err := aes.NewCipher(key[:])
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return nil, fmt.Errorf("密文数据过短")
	}

	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	return gcm.Open(nil, nonce, ciphertext, nil)
}

func RestoreBackup(filename, password string) error {
	backupDir := filepath.Join(config.C.Data.Dir, "backups")
	filePath := filepath.Join(backupDir, filepath.Base(filename))

	fileData, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read backup: %w", err)
	}

	var jsonData []byte
	if strings.HasSuffix(filename, ".enc") {
		if password == "" {
			return fmt.Errorf("加密备份需要密码")
		}
		decrypted, err := decryptData(fileData, password)
		if err != nil {
			return fmt.Errorf("failed to decrypt backup: %w", err)
		}
		jsonData = decrypted
	} else {
		jsonData = fileData
	}

	var backup BackupData
	if err := json.Unmarshal(jsonData, &backup); err != nil {
		return fmt.Errorf("failed to parse backup: %w", err)
	}

	tx := database.DB.Begin()

	tx.Where("1 = 1").Delete(&model.Task{})
	tx.Where("1 = 1").Delete(&model.EnvVar{})
	tx.Where("1 = 1").Delete(&model.Subscription{})
	tx.Where("1 = 1").Delete(&model.NotifyChannel{})
	tx.Where("1 = 1").Delete(&model.SSHKey{})
	tx.Where("1 = 1").Delete(&model.SystemConfig{})
	tx.Where("1 = 1").Delete(&model.Dependency{})

	for _, item := range backup.Tasks {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.EnvVars {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.Subs {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.Channels {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.SSHKeys {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.Configs {
		item.ID = 0
		tx.Create(&item)
	}
	for _, item := range backup.Deps {
		item.ID = 0
		tx.Create(&item)
	}

	if err := tx.Commit().Error; err != nil {
		return err
	}

	if len(backup.Scripts) > 0 {
		restoreScripts(config.C.Data.ScriptsDir, backup.Scripts)
	}

	GetSchedulerV2().ReloadAllJobs()
	return nil
}

func ListBackups() ([]map[string]interface{}, error) {
	backupDir := filepath.Join(config.C.Data.Dir, "backups")
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		return []map[string]interface{}{}, nil
	}

	var backups []map[string]interface{}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			continue
		}
		backups = append(backups, map[string]interface{}{
			"name":       entry.Name(),
			"size":       info.Size(),
			"created_at": info.ModTime(),
		})
	}

	return backups, nil
}

func DeleteBackup(filename string) error {
	backupDir := filepath.Join(config.C.Data.Dir, "backups")
	filePath := filepath.Join(backupDir, filepath.Base(filename))
	return os.Remove(filePath)
}

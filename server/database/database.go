package database

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"daidai-panel/config"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

func Init(cfg *config.DatabaseConfig) {
	dbPath := cfg.Path
	if dbPath == "" {
		dbPath = "./data/daidai.db"
	}

	dir := filepath.Dir(dbPath)
	os.MkdirAll(dir, 0755)

	customLogger := logger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags),
		logger.Config{
			SlowThreshold:             200000000,
			LogLevel:                  logger.Warn,
			IgnoreRecordNotFoundError: true,
			Colorful:                  false,
		},
	)

	var err error
	DB, err = gorm.Open(sqlite.Open(dbPath), &gorm.Config{
		Logger: customLogger,
	})
	if err != nil {
		log.Fatalf("failed to connect database: %v", err)
	}

	sqlDB, err := DB.DB()
	if err != nil {
		log.Fatalf("failed to get sql.DB: %v", err)
	}

	sqlDB.SetMaxOpenConns(1)
	sqlDB.SetMaxIdleConns(1)

	DB.Exec("PRAGMA journal_mode=WAL")
	DB.Exec("PRAGMA busy_timeout=5000")
	DB.Exec("PRAGMA foreign_keys=ON")

	log.Printf("database connected: %s", dbPath)
}

func AutoMigrate(models ...interface{}) {
	if err := DB.AutoMigrate(models...); err != nil {
		log.Fatalf("auto migrate failed: %v", err)
	}
}

type columnDef struct {
	Name    string
	SQLType string
}

func getExistingColumns(table string) map[string]bool {
	cols := make(map[string]bool)
	type pragmaRow struct {
		Name string
	}
	var rows []pragmaRow
	DB.Raw(fmt.Sprintf("PRAGMA table_info(%s)", table)).Scan(&rows)
	for _, r := range rows {
		cols[strings.ToLower(r.Name)] = true
	}
	return cols
}

func ensureTableColumns(table string, columns []columnDef) {
	existing := getExistingColumns(table)
	if len(existing) == 0 {
		return
	}
	for _, col := range columns {
		lookupName := strings.ToLower(strings.Trim(col.Name, "\""))
		if !existing[lookupName] {
			sql := fmt.Sprintf("ALTER TABLE %s ADD COLUMN %s %s", table, col.Name, col.SQLType)
			if err := DB.Exec(sql).Error; err != nil {
				log.Printf("warn: failed to add column %s.%s: %v", table, col.Name, err)
			} else {
				log.Printf("added missing column: %s.%s", table, col.Name)
			}
		}
	}
}

func EnsureColumns() {
	ensureTableColumns("tasks", []columnDef{
		{"pid", "INTEGER"},
		{"log_path", "VARCHAR(256)"},
		{"last_running_time", "REAL"},
		{"task_before", "TEXT"},
		{"task_after", "TEXT"},
		{"allow_multiple_instances", "BOOLEAN DEFAULT 0"},
		{"timeout", "INTEGER DEFAULT 300"},
		{"max_retries", "INTEGER DEFAULT 0"},
		{"retry_interval", "INTEGER DEFAULT 60"},
		{"notify_on_failure", "BOOLEAN DEFAULT 1"},
		{"notify_on_success", "BOOLEAN DEFAULT 0"},
		{"depends_on", "INTEGER"},
		{"sort_order", "INTEGER DEFAULT 0"},
		{"is_pinned", "BOOLEAN DEFAULT 0"},
	})

	ensureTableColumns("task_logs", []columnDef{
		{"log_path", "VARCHAR(256)"},
		{"duration", "REAL"},
		{"started_at", "DATETIME"},
		{"ended_at", "DATETIME"},
	})

	ensureTableColumns("env_vars", []columnDef{
		{"position", "REAL DEFAULT 10000.0"},
		{"sort_order", "INTEGER DEFAULT 0"},
		{"\"group\"", "VARCHAR(64) DEFAULT ''"},
	})

	ensureTableColumns("subscriptions", []columnDef{
		{"save_dir", "VARCHAR(512) DEFAULT ''"},
		{"ssh_key_id", "INTEGER"},
		{"alias", "VARCHAR(128) DEFAULT ''"},
		{"auto_add_task", "BOOLEAN DEFAULT 0"},
		{"auto_del_task", "BOOLEAN DEFAULT 0"},
		{"whitelist", "VARCHAR(512) DEFAULT ''"},
		{"blacklist", "VARCHAR(512) DEFAULT ''"},
		{"depend_on", "VARCHAR(512) DEFAULT ''"},
	})

	ensureTableColumns("open_apps", []columnDef{
		{"rate_limit", "INTEGER DEFAULT 100"},
		{"call_count", "INTEGER DEFAULT 0"},
	})

	ensureTableColumns("api_call_logs", []columnDef{
		{"app_name", "VARCHAR(128)"},
		{"duration", "REAL DEFAULT 0"},
	})

	ensureTableColumns("login_logs", []columnDef{
		{"method", "VARCHAR(32) DEFAULT '密码登录'"},
	})

	log.Printf("column check completed")
}

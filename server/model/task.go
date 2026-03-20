package model

import (
	"strings"
	"time"
)

const (
	TaskStatusDisabled = 0
	TaskStatusQueued   = 0.5
	TaskStatusEnabled  = 1
	TaskStatusRunning  = 2

	RunSuccess = 0
	RunFailed  = 1
)

type Task struct {
	ID                     uint       `gorm:"primarykey" json:"id"`
	Name                   string     `gorm:"size:128;not null" json:"name"`
	Command                string     `gorm:"type:text;not null" json:"command"`
	CronExpression         string     `gorm:"size:64;not null" json:"cron_expression"`
	Status                 float64    `gorm:"default:1;not null" json:"status"`
	Labels                 string     `gorm:"size:256;default:''" json:"-"`
	LastRunAt              *time.Time `json:"last_run_at"`
	LastRunStatus          *int       `json:"last_run_status"`
	Timeout                int        `gorm:"default:300" json:"timeout"`
	MaxRetries             int        `gorm:"default:0" json:"max_retries"`
	RetryInterval          int        `gorm:"default:60" json:"retry_interval"`
	NotifyOnFailure        bool       `gorm:"default:true" json:"notify_on_failure"`
	NotifyOnSuccess        bool       `gorm:"default:false" json:"notify_on_success"`
	DependsOn              *uint      `gorm:"index" json:"depends_on"`
	SortOrder              int        `gorm:"default:0" json:"sort_order"`
	IsPinned               bool       `gorm:"default:false" json:"is_pinned"`
	PID                    *int       `json:"pid"`
	LogPath                *string    `gorm:"size:256" json:"log_path"`
	LastRunningTime        *float64   `json:"last_running_time"`
	TaskBefore             *string    `gorm:"type:text" json:"task_before"`
	TaskAfter              *string    `gorm:"type:text" json:"task_after"`
	AllowMultipleInstances bool       `gorm:"default:false" json:"allow_multiple_instances"`
	CreatedAt              time.Time  `json:"created_at"`
	UpdatedAt              time.Time  `json:"updated_at"`
}

func (Task) TableName() string {
	return "tasks"
}

func (t *Task) ToDict() map[string]interface{} {
	labels := []string{}
	if t.Labels != "" {
		labels = strings.Split(t.Labels, ",")
	}

	return map[string]interface{}{
		"id":                       t.ID,
		"name":                     t.Name,
		"command":                  t.Command,
		"cron_expression":          t.CronExpression,
		"status":                   t.Status,
		"labels":                   labels,
		"last_run_at":              t.LastRunAt,
		"last_run_status":          t.LastRunStatus,
		"timeout":                  t.Timeout,
		"max_retries":              t.MaxRetries,
		"retry_interval":           t.RetryInterval,
		"notify_on_failure":        t.NotifyOnFailure,
		"depends_on":               t.DependsOn,
		"sort_order":               t.SortOrder,
		"is_pinned":                t.IsPinned,
		"pid":                      t.PID,
		"log_path":                 t.LogPath,
		"last_running_time":        t.LastRunningTime,
		"task_before":              t.TaskBefore,
		"task_after":               t.TaskAfter,
		"allow_multiple_instances": t.AllowMultipleInstances,
		"created_at":               t.CreatedAt,
		"updated_at":               t.UpdatedAt,
	}
}

func (t *Task) SetLabelsFromSlice(labels []string) {
	t.Labels = strings.Join(labels, ",")
}

func (t *Task) GetLabels() []string {
	if t.Labels == "" {
		return []string{}
	}
	return strings.Split(t.Labels, ",")
}

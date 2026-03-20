package service

import (
	"fmt"
	"log"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"daidai-panel/config"
	"daidai-panel/model"
)

var panelStartTime = time.Now()

type ResourceInfo struct {
	CPUUsage    float64 `json:"cpu_usage"`
	MemoryTotal uint64  `json:"memory_total"`
	MemoryUsed  uint64  `json:"memory_used"`
	MemoryFree  uint64  `json:"memory_free"`
	MemoryUsage float64 `json:"memory_usage"`
	DiskTotal   uint64  `json:"disk_total"`
	DiskUsed    uint64  `json:"disk_used"`
	DiskFree    uint64  `json:"disk_free"`
	DiskUsage   float64 `json:"disk_usage"`
	Uptime      string  `json:"uptime"`
	GoRoutines  int     `json:"goroutines"`
	GoVersion   string  `json:"go_version"`
	OS          string  `json:"os"`
	Arch        string  `json:"arch"`
	NumCPU      int     `json:"num_cpu"`
	DataDir     string  `json:"data_dir"`
}

func GetResourceInfo() ResourceInfo {
	info := ResourceInfo{
		GoRoutines: runtime.NumGoroutine(),
		GoVersion:  runtime.Version(),
		OS:         runtime.GOOS,
		Arch:       runtime.GOARCH,
		NumCPU:     runtime.NumCPU(),
		Uptime:     getPanelUptime(),
	}

	if config.C != nil {
		absDir, err := filepath.Abs(config.C.Data.Dir)
		if err == nil {
			info.DataDir = absDir
		} else {
			info.DataDir = config.C.Data.Dir
		}
	}

	if runtime.GOOS == "linux" {
		info.MemoryTotal, info.MemoryUsed, info.MemoryFree = getLinuxMemory()
		if info.MemoryTotal > 0 {
			info.MemoryUsage = math.Round(float64(info.MemoryUsed)/float64(info.MemoryTotal)*10000) / 100
		}

		info.DiskTotal, info.DiskUsed, info.DiskFree = getLinuxDisk()
		if info.DiskTotal > 0 {
			info.DiskUsage = math.Round(float64(info.DiskUsed)/float64(info.DiskTotal)*10000) / 100
		}

		info.CPUUsage = getLinuxCPU()
	}

	return info
}

func getPanelUptime() string {
	dur := time.Since(panelStartTime)
	days := int(dur.Hours() / 24)
	hours := int(dur.Hours()) % 24
	mins := int(dur.Minutes()) % 60

	if days > 0 {
		return strconv.Itoa(days) + "天" + strconv.Itoa(hours) + "时" + strconv.Itoa(mins) + "分"
	}
	if hours > 0 {
		return strconv.Itoa(hours) + "时" + strconv.Itoa(mins) + "分"
	}
	return strconv.Itoa(mins) + "分"
}

func getLinuxMemory() (total, used, free uint64) {
	out, err := exec.Command("free", "-b").Output()
	if err != nil {
		return
	}
	lines := strings.Split(string(out), "\n")
	if len(lines) < 2 {
		return
	}
	fields := strings.Fields(lines[1])
	if len(fields) < 4 {
		return
	}
	total, _ = strconv.ParseUint(fields[1], 10, 64)
	used, _ = strconv.ParseUint(fields[2], 10, 64)
	free, _ = strconv.ParseUint(fields[3], 10, 64)
	return
}

func getLinuxDisk() (total, used, free uint64) {
	out, err := exec.Command("df", "-B1", "/").Output()
	if err != nil {
		return
	}
	lines := strings.Split(string(out), "\n")
	if len(lines) < 2 {
		return
	}
	fields := strings.Fields(lines[1])
	if len(fields) < 4 {
		return
	}
	total, _ = strconv.ParseUint(fields[1], 10, 64)
	used, _ = strconv.ParseUint(fields[2], 10, 64)
	free, _ = strconv.ParseUint(fields[3], 10, 64)
	return
}

func getLinuxCPU() float64 {
	readStat := func() (idle, total uint64) {
		out, err := os.ReadFile("/proc/stat")
		if err != nil {
			return
		}
		lines := strings.Split(string(out), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "cpu ") {
				fields := strings.Fields(line)
				if len(fields) < 5 {
					return
				}
				var sum uint64
				for _, f := range fields[1:] {
					v, _ := strconv.ParseUint(f, 10, 64)
					sum += v
				}
				idleVal, _ := strconv.ParseUint(fields[4], 10, 64)
				return idleVal, sum
			}
		}
		return
	}

	idle1, total1 := readStat()
	time.Sleep(500 * time.Millisecond)
	idle2, total2 := readStat()

	totalDelta := total2 - total1
	idleDelta := idle2 - idle1
	if totalDelta == 0 {
		return 0
	}
	usage := float64(totalDelta-idleDelta) / float64(totalDelta) * 100
	return math.Round(usage*100) / 100
}

var (
	resourceCheckOnce sync.Once
	resourceCheckStop chan struct{}
	lastWarnTime      time.Time
)

func StartResourceWatcher() {
	resourceCheckOnce.Do(func() {
		resourceCheckStop = make(chan struct{})
		go resourceWatchLoop()
		log.Println("resource watcher started (interval: 5min)")
	})
}

func StopResourceWatcher() {
	if resourceCheckStop != nil {
		close(resourceCheckStop)
	}
}

func resourceWatchLoop() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	time.Sleep(30 * time.Second)
	checkResourceThresholds()

	for {
		select {
		case <-ticker.C:
			checkResourceThresholds()
		case <-resourceCheckStop:
			return
		}
	}
}

func checkResourceThresholds() {
	if model.GetConfig("notify_on_resource_warn", "false") != "true" {
		return
	}

	if time.Since(lastWarnTime) < 30*time.Minute {
		return
	}

	info := GetResourceInfo()
	cpuThreshold := float64(model.GetConfigInt("cpu_warn", 80))
	memThreshold := float64(model.GetConfigInt("memory_warn", 80))
	diskThreshold := float64(model.GetConfigInt("disk_warn", 90))

	var warnings []string
	if info.CPUUsage > cpuThreshold {
		warnings = append(warnings, fmt.Sprintf("CPU 使用率 %.1f%% (阈值 %.0f%%)", info.CPUUsage, cpuThreshold))
	}
	if info.MemoryUsage > memThreshold {
		warnings = append(warnings, fmt.Sprintf("内存使用率 %.1f%% (阈值 %.0f%%)", info.MemoryUsage, memThreshold))
	}
	if info.DiskUsage > diskThreshold {
		warnings = append(warnings, fmt.Sprintf("磁盘使用率 %.1f%% (阈值 %.0f%%)", info.DiskUsage, diskThreshold))
	}

	if len(warnings) > 0 {
		lastWarnTime = time.Now()
		content := "以下资源使用超过告警阈值：\n\n" + strings.Join(warnings, "\n")
		go SendNotification("系统资源告警", content)
		log.Printf("resource warn: %s", strings.Join(warnings, "; "))
	}
}

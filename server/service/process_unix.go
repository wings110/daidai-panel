//go:build !windows

package service

import (
	"os"
	"os/exec"
	"syscall"
)

func setPgid(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func killGroup(p *os.Process) {
	syscall.Kill(-p.Pid, syscall.SIGKILL)
}

func killGroupByPid(pid int) {
	syscall.Kill(-pid, syscall.SIGKILL)
}

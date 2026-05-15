package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/alecthomas/kong"
	"github.com/charmbracelet/lipgloss"
	clog "github.com/charmbracelet/log"
	"github.com/schollz/progressbar/v3"
)

// ── Patterns ──────────────────────────────────────────────────────────────────

const picoPortPattern = "/dev/tty.usbmodem*"

// ── Styles ────────────────────────────────────────────────────────────────────

var (
	styleHeader  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("14"))
	styleSuccess = lipgloss.NewStyle().Foreground(lipgloss.Color("2"))
	styleWarning = lipgloss.NewStyle().Foreground(lipgloss.Color("3"))
	styleError   = lipgloss.NewStyle().Foreground(lipgloss.Color("1"))
	styleInfo    = lipgloss.NewStyle().Foreground(lipgloss.Color("4"))
	styleDim     = lipgloss.NewStyle().Faint(true)
)

var logger *clog.Logger

func initLogger(verbose int) {
	level := clog.WarnLevel
	if verbose >= 2 {
		level = clog.DebugLevel
	} else if verbose >= 1 {
		level = clog.InfoLevel
	}
	logger = clog.NewWithOptions(os.Stderr, clog.Options{Level: level})
}

func logInfo(format string, a ...any)    { fmt.Fprintf(os.Stderr, styleInfo.Render(fmt.Sprintf(format, a...))) }
func logSuccess(format string, a ...any) { fmt.Fprintf(os.Stderr, styleSuccess.Render(fmt.Sprintf(format, a...))) }
func logWarn(format string, a ...any)    { fmt.Fprintf(os.Stderr, styleWarning.Render(fmt.Sprintf(format, a...))) }
func logErr(format string, a ...any)     { fmt.Fprintf(os.Stderr, styleError.Render(fmt.Sprintf(format, a...))) }
func logFatal(format string, a ...any)   { logErr(format, a...); os.Exit(1) }
func logDetail(format string, a ...any) {
	if logger != nil {
		logger.Debug(fmt.Sprintf(format, a...))
	}
}

// ── CLI ───────────────────────────────────────────────────────────────────────

var cli struct {
	Port    string `short:"p" help:"Serial port (default: first /dev/tty.usbmodem*)." placeholder:"PORT"`
	DryRun  bool   `help:"Show what would be sent without touching the device." name:"dry-run"`
	Verbose int    `short:"v" type:"counter" help:"Increase verbosity (-v, -vv)."`

	Upload UploadCmd `cmd:"" default:"withargs" help:"Push app code and examples to device."`
	Data   DataCmd   `cmd:"" help:"Push data files (JSON) to device."`
	Logs   LogsCmd   `cmd:"" help:"Stream serial output from device."`
	Reset  ResetCmd  `cmd:"" help:"Soft-reset the device."`
}

type UploadCmd struct {
	Force bool `short:"f" help:"Re-upload all files, skipping nothing."`
}

type DataCmd struct{}
type LogsCmd struct{}
type ResetCmd struct{}

func (c *UploadCmd) Run() error { uploadFiles(c.Force); return nil }
func (c *DataCmd) Run() error   { pushData(); return nil }
func (c *LogsCmd) Run() error   { tailLogs(); return nil }
func (c *ResetCmd) Run() error  { resetDevice(); return nil }

// ── Port detection ────────────────────────────────────────────────────────────

func findPort() string {
	if cli.Port != "" {
		return cli.Port
	}
	ports, _ := filepath.Glob(picoPortPattern)
	if len(ports) == 0 {
		logFatal("No device found at %s\nConnect the Badger and try again.\n", picoPortPattern)
	}
	if len(ports) > 1 {
		logWarn("Multiple devices found; using %s. Use --port to specify.\n", ports[0])
	}
	return ports[0]
}

// ── mpremote helpers ──────────────────────────────────────────────────────────

func mpremoteArgs(port string, args ...string) []string {
	return append([]string{"connect", port}, args...)
}

func runMpremote(port string, args ...string) (string, error) {
	if cli.DryRun {
		logDetail("DRY RUN: mpremote %s\n", strings.Join(args, " "))
		return "", nil
	}
	cmd := exec.Command("mpremote", mpremoteArgs(port, args...)...)
	out, err := cmd.CombinedOutput()
	return strings.TrimSpace(string(out)), err
}

func mpremoteExec(port, code string) error {
	if cli.DryRun {
		logDetail("DRY RUN: exec %q\n", code)
		return nil
	}
	cmd := exec.Command("mpremote", mpremoteArgs(port, "exec", code)...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// ensureDir creates a directory on the device, ignoring "already exists" errors.
func ensureDir(port, remotePath string) {
	code := fmt.Sprintf(
		"import os\ntry:\n    os.mkdir(%q)\nexcept OSError:\n    pass\n",
		remotePath,
	)
	if err := mpremoteExec(port, code); err != nil {
		logWarn("Could not ensure dir %s: %v\n", remotePath, err)
	}
}

// copyFile copies a local file to a remote path on the device.
func copyFile(port, localPath, remotePath string) error {
	if cli.DryRun {
		logDetail("DRY RUN: cp %s → :%s\n", localPath, remotePath)
		return nil
	}
	cmd := exec.Command("mpremote", mpremoteArgs(port, "fs", "cp", localPath, ":"+remotePath)...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("cp %s: %w\n%s", localPath, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// ── Upload (code) ─────────────────────────────────────────────────────────────

// filesInDir returns all files recursively under dir (relative paths from dir root).
func filesInDir(dir string) ([]string, error) {
	var files []string
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(dir, path)
		files = append(files, rel)
		return nil
	})
	return files, err
}

// uploadIgnored returns true for files that should never be pushed.
func uploadIgnored(rel string) bool {
	base := filepath.Base(rel)
	switch {
	case base == ".DS_Store":
		return true
	case strings.HasSuffix(base, ".pyc"):
		return true
	case strings.Contains(rel, "__pycache__"):
		return true
	case strings.HasSuffix(base, ".local.json"):
		return true
	}
	return false
}

func uploadFiles(force bool) {
	port := findPort()
	logInfo("Uploading to %s...\n", port)

	// apps/ → /system/apps/ on device (BadgeOS v4 layout)
	type syncDir struct {
		local  string
		remote string
	}
	dirs := []syncDir{
		{"apps", "/system/apps"},
	}

	// Collect all files
	type job struct {
		local  string
		remote string
	}
	var jobs []job
	for _, d := range dirs {
		files, err := filesInDir(d.local)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			logFatal("Failed to list %s: %v\n", d.local, err)
		}
		for _, rel := range files {
			if uploadIgnored(rel) {
				continue
			}
			local := filepath.Join(d.local, rel)
			remote := d.remote + "/" + filepath.ToSlash(rel)
			jobs = append(jobs, job{local, remote})
		}
	}

	if len(jobs) == 0 {
		logWarn("No files found to upload.\n")
		return
	}

	// Ensure remote directories exist
	remoteDirs := map[string]bool{}
	for _, j := range jobs {
		dir := filepath.Dir(j.remote)
		if dir != "/" {
			remoteDirs[dir] = true
		}
	}
	for dir := range remoteDirs {
		ensureDir(port, dir)
	}

	// Upload files with progress bar
	bar := progressbar.NewOptions(len(jobs),
		progressbar.OptionSetWriter(os.Stderr),
		progressbar.OptionSetDescription("Uploading"),
		progressbar.OptionShowCount(),
		progressbar.OptionSetTheme(progressbar.Theme{
			Saucer:        "=",
			SaucerHead:    ">",
			SaucerPadding: " ",
			BarStart:      "[",
			BarEnd:        "]",
		}),
	)

	failed := 0
	for _, j := range jobs {
		if err := copyFile(port, j.local, j.remote); err != nil {
			logWarn("\nFailed: %v\n", err)
			failed++
		}
		bar.Add(1)
	}

	fmt.Fprintln(os.Stderr)
	if failed == 0 {
		logSuccess("Upload complete: %d files pushed.\n", len(jobs))
	} else {
		logWarn("Upload complete with %d error(s). %d files pushed.\n", failed, len(jobs)-failed)
	}
}

// ── Push data files ────────────────────────────────────────────────────────────

func pushData() {
	port := findPort()
	logInfo("Pushing data files to %s...\n", port)

	// Walk apps/ and push only .json files (quick refresh without re-uploading .py/.png)
	files, err := filesInDir("apps")
	if err != nil {
		logFatal("Failed to list apps/: %v\n", err)
	}

	pushed := 0
	for _, rel := range files {
		if uploadIgnored(rel) || !strings.HasSuffix(rel, ".json") {
			continue
		}
		local := filepath.Join("apps", rel)
		remote := "/system/apps/" + filepath.ToSlash(rel)
		logInfo("  %s → %s\n", styleDim.Render(local), remote)
		if err := copyFile(port, local, remote); err != nil {
			logWarn("  Failed: %v\n", err)
			continue
		}
		pushed++
	}

	logSuccess("Data push complete: %d files.\n", pushed)
}

// ── Tail logs ─────────────────────────────────────────────────────────────────

func tailLogs() {
	port := findPort()
	logInfo("Streaming serial output from %s (Ctrl+C to stop)...\n", port)
	logInfo("Waiting for output — navigate to an app on the device.\n")

	for {
		// Configure port: 115200 baud, raw, no echo
		exec.Command("stty", "-f", port, "115200", "raw", "-echo", "cs8", "-parenb", "-cstopb").Run()

		// O_NOCTTY: don't make this the controlling terminal
		// O_NONBLOCK: don't block on open waiting for DCD
		f, err := os.OpenFile(port, os.O_RDONLY|syscall.O_NOCTTY|syscall.O_NONBLOCK, 0)
		if err != nil {
			time.Sleep(300 * time.Millisecond)
			continue
		}
		// Switch to blocking reads once the port is open
		syscall.SetNonblock(int(f.Fd()), false)

		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.Contains(line, "Traceback") || strings.Contains(line, "Error") {
				fmt.Println(styleError.Render(line))
			} else {
				fmt.Println(line)
			}
		}

		f.Close()
		logWarn("\nDevice disconnected — waiting to reconnect...\n")
		time.Sleep(300 * time.Millisecond)
	}
}

// ── Reset ─────────────────────────────────────────────────────────────────────

func resetDevice() {
	port := findPort()
	logInfo("Resetting %s...\n", port)
	if _, err := runMpremote(port, "reset"); err != nil {
		logErr("Reset failed: %v\n", err)
		return
	}
	logSuccess("Device reset.\n")
}

// ── io.Discard alias for older Go ─────────────────────────────────────────────

var _ io.Writer = io.Discard

// ── main ──────────────────────────────────────────────────────────────────────

func main() {
	// Dedicated goroutine so Ctrl+C always exits, even when another goroutine
	// is stuck in an uninterruptible kernel sleep (e.g. blocking read on a
	// USB serial device). os.Exit terminates via the _exit syscall, which the
	// kernel always honours regardless of goroutine state.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigCh
		fmt.Fprintln(os.Stderr)
		os.Exit(0)
	}()

	ctx := kong.Parse(&cli,
		kong.Name("badger-push"),
		kong.Description("Push code and data to Badger 2350 W."),
		kong.UsageOnError(),
		kong.ConfigureHelp(kong.HelpOptions{Compact: true}),
	)
	initLogger(cli.Verbose)
	if err := ctx.Run(); err != nil {
		logFatal("%v\n", err)
	}
}

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

// RP2350 presents this volume when in BOOTSEL (UF2 mass-storage) mode.
// RP2040 boards use RPI-RP2.
var bootselVolumes = []string{"/Volumes/RP2350", "/Volumes/RPI-RP2"}

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

// confirmPrompt prints msg + " [y/N] " and returns true only if the user types
// y or yes. Skipped (returns true) when --yes or --dry-run is active.
func confirmPrompt(msg string) bool {
	if cli.Yes || cli.DryRun {
		return true
	}
	fmt.Fprintf(os.Stderr, styleWarning.Render(msg+" [y/N] "))
	line, _ := bufio.NewReader(os.Stdin).ReadString('\n')
	answer := strings.TrimSpace(strings.ToLower(line))
	fmt.Fprintln(os.Stderr)
	return answer == "y" || answer == "yes"
}

// ── CLI ───────────────────────────────────────────────────────────────────────

var cli struct {
	Port    string `short:"p" help:"Serial port (default: first /dev/tty.usbmodem*)." placeholder:"PORT"`
	DryRun  bool   `help:"Show what would be sent without touching the device." name:"dry-run"`
	Yes     bool   `short:"y" help:"Skip confirmation prompts." name:"yes"`
	Verbose int    `short:"v" type:"counter" help:"Increase verbosity (-v, -vv)."`

	Upload UploadCmd `cmd:"" default:"withargs" help:"Push app code via mpremote (requires REPL access)."`
	Disk   DiskCmd   `cmd:"" help:"Deploy all apps via USB Disk Mode (double-tap RESET → BADGER volume)."`
	Data   DataCmd   `cmd:"" help:"Push data files (JSON) via mpremote."`
	Docs   DocsCmd   `cmd:"" help:"Serve docs/ locally on localhost:8080 for BLE testing (use Chrome/Edge)."`
	Logs   LogsCmd   `cmd:"" help:"Stream serial output from device."`
	Reset  ResetCmd  `cmd:"" help:"Soft-reset the device."`
	Flash  FlashCmd  `cmd:"" help:"Flash UF2 firmware via BOOTSEL mass-storage mode."`
}

type UploadCmd struct {
	Force bool     `short:"f" help:"Re-upload all files, skipping nothing."`
	Apps  []string `arg:"" optional:"" name:"app" help:"App names to push (default: all apps)."`
}

type DiskCmd struct {
	Keep []string `help:"Factory app names to preserve (default: removes the_compendium, hydrate, mass_storage)." name:"keep"`
}
type DataCmd struct {
	Apps []string `arg:"" optional:"" name:"app" help:"App names to push data for (default: all apps)."`
}
type DocsCmd struct{}
type LogsCmd struct{}
type ResetCmd struct{}
type FlashCmd struct {
	UF2 string `arg:"" help:"Path to .uf2 firmware file." type:"existingfile"`
}

func (c *UploadCmd) Run() error { uploadFiles(c.Force, c.Apps); return nil }
func (c *DiskCmd) Run() error   { deployDisk(c.Keep); return nil }
func (c *DataCmd) Run() error   { pushData(c.Apps); return nil }
func (c *DocsCmd) Run() error   { serveDocs(); return nil }
func (c *LogsCmd) Run() error   { tailLogs(); return nil }
func (c *ResetCmd) Run() error  { resetDevice(); return nil }
func (c *FlashCmd) Run() error  { flashFirmware(c.UF2); return nil }

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

// copyFile copies a local file to a remote path on the device via mpremote.
// mpremote uses the MicroPython REPL filesystem protocol, so this works in
// normal (non-disk) mode — the device does not need to be in BOOTSEL/MSC mode.
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

// ── USB Disk Mode deploy ──────────────────────────────────────────────────────

// diskVolume is the macOS mount point of the Badger USB Disk Mode volume.
// Update this if a firmware release changes the FAT label.
const diskVolume = "/Volumes/BADGER"

// defaultFactoryAppsToRemove lists built-in apps stripped from the device on
// every disk deploy. These are present after every reflash; remove from this
// list if you want to keep one of them.
var defaultFactoryAppsToRemove = []string{"badge", "the_compendium", "hydrate", "mass_storage"}

// deployDisk copies app directories to the Badger USB Disk Mode volume and
// removes unwanted factory apps.
func deployDisk(keep []string) {
	keepSet := make(map[string]bool, len(keep))
	for _, k := range keep {
		keepSet[k] = true
	}
	volName := filepath.Base(diskVolume)

	// Check or wait for the volume.
	if _, err := os.Stat(diskVolume); err != nil {
		logInfo("%s volume not found.\n", volName)
		logInfo("  1. Connect the Badger via USB-C.\n")
		logInfo("  2. Double-tap the RESET button on the back.\n")
		logInfo("  3. Wait for a disk named %q to appear.\n", volName)
		fmt.Fprintf(os.Stderr, styleInfo.Render("Waiting for "+volName+" volume"))
		for i := 0; i < 60; i++ {
			if _, err := os.Stat(diskVolume); err == nil {
				break
			}
			fmt.Fprintf(os.Stderr, styleInfo.Render("."))
			time.Sleep(500 * time.Millisecond)
		}
		fmt.Fprintln(os.Stderr)
		if _, err := os.Stat(diskVolume); err != nil {
			logFatal("Timed out — %s volume not found.\n", volName)
		}
	}
	logSuccess("Found %s\n", diskVolume)

	// Locate apps/ relative to cwd or one level up (script/ → repo root).
	appsDir := "apps"
	if _, err := os.Stat(appsDir); os.IsNotExist(err) {
		appsDir = filepath.Join("..", "apps")
	}

	// Enumerate app directories to copy (skip menu — keep factory menu).
	entries, err := os.ReadDir(appsDir)
	if err != nil {
		logFatal("Cannot read %s/: %v\n", appsDir, err)
	}

	var appDirs []string
	for _, e := range entries {
		if e.IsDir() && e.Name() != "menu" {
			appDirs = append(appDirs, e.Name())
		}
	}
	if len(appDirs) == 0 {
		logWarn("No app directories found under %s/ (excluding menu).\n", appsDir)
		return
	}

	for _, name := range appDirs {
		localPath, _ := filepath.Abs(filepath.Join(appsDir, name))
		remotePath := diskVolume + "/apps"

		logInfo("  Copying %s → %s/apps/\n", name, volName)

		// Delete the existing app directory on the volume first (if present),
		// then duplicate the local directory.  Both operations go through Finder
		// to satisfy macOS 15 FSKit entitlement requirements on FAT32 volumes.
		script := fmt.Sprintf(`
set srcFolder to POSIX file %q
set dstFolder to POSIX file %q
tell application "Finder"
    if exists folder %q of folder dstFolder then
        delete folder %q of folder dstFolder
    end if
    duplicate folder srcFolder to folder dstFolder
end tell
`, localPath, remotePath, name, name)

		cmd := exec.Command("osascript", "-e", script)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			logWarn("  Failed to copy %s: %v\n", name, err)
		}
	}

	// Remove unwanted factory apps from the volume.
	appsRemotePath := diskVolume + "/apps"
	for _, name := range defaultFactoryAppsToRemove {
		if keepSet[name] {
			continue
		}
		logInfo("  Removing factory app: %s\n", name)
		script := fmt.Sprintf(`
set dstFolder to POSIX file %q
tell application "Finder"
    if exists folder %q of folder dstFolder then
        delete folder %q of folder dstFolder
    end if
end tell
`, appsRemotePath, name, name)
		cmd := exec.Command("osascript", "-e", script)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			logWarn("  Failed to remove %s: %v\n", name, err)
		}
	}

	logSuccess("Done. Safely unmount the %s volume (Finder → eject).\n", volName)
	logInfo("The badge will reboot into the menu when unmounted.\n")
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

// appNameFromRel returns the top-level directory component of a relative path
// (e.g. "url_share/__init__.py" → "url_share").
func appNameFromRel(rel string) string {
	parts := strings.SplitN(filepath.ToSlash(rel), "/", 2)
	return parts[0]
}

// inFilter returns true if name is in filter, or filter is empty (match all).
func inFilter(filter []string, name string) bool {
	if len(filter) == 0 {
		return true
	}
	for _, f := range filter {
		if f == name {
			return true
		}
	}
	return false
}

func uploadFiles(force bool, filterApps []string) {
	prompt := "This will overwrite all apps on the device. Continue?"
	if len(filterApps) > 0 {
		prompt = fmt.Sprintf("Push [%s] to device. Continue?", strings.Join(filterApps, ", "))
	}
	if !confirmPrompt(prompt) {
		logInfo("Aborted.\n")
		return
	}

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

	// Collect files, filtered to named apps if specified.
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
			if !inFilter(filterApps, appNameFromRel(rel)) {
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

func pushData(filterApps []string) {
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
		if !inFilter(filterApps, appNameFromRel(rel)) {
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

// ── Serve docs ────────────────────────────────────────────────────────────────

func serveDocs() {
	docsDir := "docs"
	if _, err := os.Stat(docsDir); os.IsNotExist(err) {
		docsDir = filepath.Join("..", "docs")
	}
	abs, err := filepath.Abs(docsDir)
	if err != nil {
		logFatal("Could not resolve docs/ path: %v\n", err)
	}
	if _, err := os.Stat(abs); err != nil {
		logFatal("docs/ directory not found (looked at %s)\n", abs)
	}

	const httpPort = "8080"
	logSuccess("Serving %s at http://localhost:%s\n", abs, httpPort)
	logInfo("Open in Chrome or Edge — Web Bluetooth requires a secure context (localhost).\n")
	logInfo("Press Ctrl+C to stop.\n")

	cmd := exec.Command("python3", "-m", "http.server", httpPort)
	cmd.Dir = abs
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		logErr("Server exited: %v\n", err)
	}
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

// ── Flash firmware ────────────────────────────────────────────────────────────

func findBootselVolume() string {
	for _, v := range bootselVolumes {
		if _, err := os.Stat(v); err == nil {
			return v
		}
	}
	return ""
}

// uf2Copy writes src into destDir using raw Go I/O. This avoids the macOS
// extended-attribute metadata that `cp` can attach to FAT32 volumes, which
// confuses some UF2 bootloaders.
func uf2Copy(src, destDir string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.OpenFile(
		filepath.Join(destDir, filepath.Base(src)),
		os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644,
	)
	if err != nil {
		return err
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	// The device may reboot (and unmount the volume) before Sync returns; that's fine.
	_ = out.Sync()
	return nil
}

func flashFirmware(uf2Path string) {
	if !confirmPrompt("This will overwrite the device firmware. Continue?") {
		logInfo("Aborted.\n")
		return
	}

	// Check whether the device is already in BOOTSEL mode.
	vol := findBootselVolume()
	if vol == "" {
		logInfo("Device not in BOOTSEL mode.\n")
		logInfo("  1. Hold the BOOTSEL button on the Badger.\n")
		logInfo("  2. Press RESET (or unplug and replug while holding BOOTSEL).\n")
		logInfo("  3. Release BOOTSEL once the USB drive mounts.\n")
		fmt.Fprintf(os.Stderr, styleInfo.Render("Press Enter when ready (or Ctrl+C to abort): "))
		bufio.NewReader(os.Stdin).ReadString('\n')

		fmt.Fprintf(os.Stderr, styleInfo.Render("Waiting for RP2350 volume"))
		for i := 0; i < 30; i++ {
			vol = findBootselVolume()
			if vol != "" {
				break
			}
			fmt.Fprintf(os.Stderr, styleInfo.Render("."))
			time.Sleep(500 * time.Millisecond)
		}
		fmt.Fprintln(os.Stderr)
		if vol == "" {
			logFatal("Timed out — RP2350 volume not found. Was BOOTSEL held during reset?\n")
		}
	}

	logSuccess("Found %s\n", vol)
	logInfo("Copying %s → %s...\n", filepath.Base(uf2Path), vol)

	if err := uf2Copy(uf2Path, vol); err != nil {
		logFatal("Flash failed: %v\n", err)
	}

	// Wait for the BOOTSEL volume to disappear — the device has accepted the
	// firmware and is rebooting.
	fmt.Fprintf(os.Stderr, styleInfo.Render("Waiting for device to reboot"))
	for i := 0; i < 20; i++ {
		if findBootselVolume() == "" {
			break
		}
		fmt.Fprintf(os.Stderr, styleInfo.Render("."))
		time.Sleep(500 * time.Millisecond)
	}

	// Wait for the serial port to reappear (device running MicroPython again).
	for i := 0; i < 20; i++ {
		ports, _ := filepath.Glob(picoPortPattern)
		if len(ports) > 0 {
			fmt.Fprintln(os.Stderr)
			logSuccess("Device ready on %s\n", ports[0])
			return
		}
		fmt.Fprintf(os.Stderr, styleInfo.Render("."))
		time.Sleep(500 * time.Millisecond)
	}
	fmt.Fprintln(os.Stderr)
	logSuccess("Firmware flashed. No serial port detected yet — give it a moment.\n")
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

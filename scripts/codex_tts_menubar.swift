import AppKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private var statusItem: NSStatusItem!
    private let menu = NSMenu()
    private let toggleItem = NSMenuItem(title: "", action: #selector(toggleMute), keyEquivalent: "")
    private let quitItem = NSMenuItem(title: "Quit Codex TTS Menu", action: #selector(quitApp), keyEquivalent: "q")

    private let statePath: String = {
        if let fromEnv = ProcessInfo.processInfo.environment["CODEX_TTS_MUTE_STATE"], !fromEnv.isEmpty {
            return fromEnv
        }
        return NSString(string: "~/Library/Application Support/codex-tts-mcp/mute_state.json").expandingTildeInPath
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        toggleItem.target = self
        quitItem.target = self
        menu.delegate = self
        menu.addItem(toggleItem)
        menu.addItem(NSMenuItem.separator())
        menu.addItem(quitItem)
        statusItem.menu = menu
        refreshUI()
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshUI()
    }

    @objc private func toggleMute() {
        let nextMuted = !readMuted()
        writeMuted(nextMuted)
        refreshUI()
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    private func refreshUI() {
        let muted = readMuted()
        statusItem.button?.title = muted ? "CodexTTS:Mute" : "CodexTTS:On"
        toggleItem.title = muted ? "Unmute Announcer" : "Mute Announcer"
    }

    private func readMuted() -> Bool {
        let path = statePath
        guard FileManager.default.fileExists(atPath: path) else {
            return false
        }
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else {
            return false
        }
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return false
        }
        return (object["muted"] as? Bool) ?? false
    }

    private func writeMuted(_ muted: Bool) {
        let url = URL(fileURLWithPath: statePath)
        let dir = url.deletingLastPathComponent()
        _ = try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        let payload: [String: Any] = ["muted": muted]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else {
            return
        }
        try? data.write(to: url, options: .atomic)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()

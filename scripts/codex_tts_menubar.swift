import AppKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private struct SpeechSettings {
        let voice: String
        let rate: Int
    }

    private var statusItem: NSStatusItem!
    private let menu = NSMenu()
    private let toggleItem = NSMenuItem(title: "", action: #selector(toggleMute), keyEquivalent: "")
    private let settingsItem = NSMenuItem(title: "Settings…", action: #selector(openSettings), keyEquivalent: ",")
    private let quitItem = NSMenuItem(title: "Quit Codex TTS Menu", action: #selector(quitApp), keyEquivalent: "q")

    private let statePath: String = {
        if let fromEnv = ProcessInfo.processInfo.environment["CODEX_TTS_MUTE_STATE"], !fromEnv.isEmpty {
            return fromEnv
        }
        return NSString(string: "~/Library/Application Support/codex-tts-mcp/mute_state.json").expandingTildeInPath
    }()

    private let settingsPath: String = {
        if let fromEnv = ProcessInfo.processInfo.environment["CODEX_TTS_SETTINGS_PATH"], !fromEnv.isEmpty {
            return fromEnv
        }
        return NSString(string: "~/Library/Application Support/codex-tts-mcp/speech_settings.json").expandingTildeInPath
    }()

    private let defaultVoice: String = {
        let value = ProcessInfo.processInfo.environment["CODEX_TTS_VOICE"] ?? "Samantha"
        return value.isEmpty ? "Samantha" : value
    }()

    private let defaultRate: Int = {
        let raw = ProcessInfo.processInfo.environment["CODEX_TTS_RATE"] ?? "190"
        return Int(raw) ?? 190
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        toggleItem.target = self
        settingsItem.target = self
        quitItem.target = self
        menu.delegate = self
        menu.addItem(toggleItem)
        menu.addItem(settingsItem)
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

    @objc private func openSettings() {
        let current = readSpeechSettings()

        let voiceField = NSTextField(string: current.voice)
        let rateField = NSTextField(string: String(current.rate))
        voiceField.frame = NSRect(x: 0, y: 0, width: 250, height: 24)
        rateField.frame = NSRect(x: 0, y: 0, width: 80, height: 24)

        let voiceLabel = NSTextField(labelWithString: "Voice")
        let rateLabel = NSTextField(labelWithString: "Rate (80-400)")

        let voiceRow = NSStackView(views: [voiceLabel, voiceField])
        voiceRow.orientation = .horizontal
        voiceRow.spacing = 8
        voiceRow.alignment = .firstBaseline

        let rateRow = NSStackView(views: [rateLabel, rateField])
        rateRow.orientation = .horizontal
        rateRow.spacing = 8
        rateRow.alignment = .firstBaseline

        let stack = NSStackView(views: [voiceRow, rateRow])
        stack.orientation = .vertical
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 4, left: 4, bottom: 4, right: 4)

        let alert = NSAlert()
        alert.messageText = "Codex TTS Settings"
        alert.informativeText = "Set default voice and speaking rate."
        alert.addButton(withTitle: "Save")
        alert.addButton(withTitle: "Cancel")
        alert.accessoryView = stack

        let response = alert.runModal()
        if response != .alertFirstButtonReturn {
            return
        }

        let voice = voiceField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let rateRaw = rateField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)

        guard isValidVoice(voice) else {
            showError("Voice must be 1-64 chars using letters, numbers, spaces, _, ', (, ), -.")
            return
        }
        guard let rate = Int(rateRaw), (80...400).contains(rate) else {
            showError("Rate must be a number between 80 and 400.")
            return
        }

        writeSpeechSettings(SpeechSettings(voice: voice, rate: rate))
        refreshUI()
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    private func refreshUI() {
        let muted = readMuted()
        let settings = readSpeechSettings()

        toggleItem.title = muted ? "Unmute Announcer" : "Mute Announcer"
        settingsItem.title = "Settings… (Voice: \(settings.voice), Rate: \(settings.rate))"

        guard let button = statusItem.button else {
            return
        }
        let icon = muted ? "🤖🤐" : "🤖💬"
        button.title = "\(icon) CodexTTS"
        button.toolTip = muted ? "Codex TTS muted" : "Codex TTS on"
        button.image = nil
    }

    private func isValidVoice(_ value: String) -> Bool {
        if value.isEmpty || value.count > 64 {
            return false
        }
        return value.range(of: "^[A-Za-z0-9 _'()\\-]+$", options: .regularExpression) != nil
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

    private func readSpeechSettings() -> SpeechSettings {
        let path = settingsPath
        guard FileManager.default.fileExists(atPath: path),
              let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return SpeechSettings(voice: defaultVoice, rate: defaultRate)
        }

        let voice = (object["voice"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
        let rate = object["rate"] as? Int

        let finalVoice = (voice != nil && isValidVoice(voice!)) ? voice! : defaultVoice
        let finalRate = ((rate ?? defaultRate) >= 80 && (rate ?? defaultRate) <= 400) ? (rate ?? defaultRate) : defaultRate

        return SpeechSettings(voice: finalVoice, rate: finalRate)
    }

    private func writeSpeechSettings(_ settings: SpeechSettings) {
        let url = URL(fileURLWithPath: settingsPath)
        let dir = url.deletingLastPathComponent()
        _ = try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        let payload: [String: Any] = ["voice": settings.voice, "rate": settings.rate]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else {
            return
        }
        try? data.write(to: url, options: .atomic)
    }

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Invalid Settings"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()

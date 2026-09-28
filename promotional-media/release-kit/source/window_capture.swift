import AppKit
import ScreenCaptureKit
import AVFoundation

// Capture a single identity-checked window, even when another app overlaps it.
final class RecordingDelegate: NSObject, SCRecordingOutputDelegate {
    var finished = false
    var error: Error?
    func recordingOutputDidStartRecording(_ output: SCRecordingOutput) {
        print("RECORDING"); fflush(stdout)
    }
    func recordingOutputDidFinishRecording(_ output: SCRecordingOutput) { finished = true }
    func recordingOutput(_ output: SCRecordingOutput, didFailWithError error: Error) {
        self.error = error; finished = true
    }
}

@main struct Capture {
    @MainActor static func main() async throws {
        _ = NSApplication.shared
        let args = CommandLine.arguments
        guard args.count >= 4, let pid = Int32(args[1]) else { fatalError("PID output-path expected-title [seconds]") }
        let path = args[2], expectedTitle = args[3]
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
        let windows = content.windows.filter { $0.owningApplication?.processID == pid && $0.title == expectedTitle }
        guard windows.count == 1 else { fatalError("Expected exactly one matching PID and profile window") }
        let window = windows[0]
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = Int(window.frame.width) * 2
        config.height = Int(window.frame.height) * 2
        config.ignoreShadowsSingleWindow = true
        config.captureResolution = .best
        config.minimumFrameInterval = CMTime(value: 1, timescale: 30)
        config.queueDepth = 6
        config.capturesAudio = false
        config.showsCursor = args.count > 4
        if args.count == 4 {
            let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
            let bitmap = NSBitmapImageRep(cgImage: image)
            try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: path))
            print("PNG \(image.width)x\(image.height) window \(window.windowID) PID \(pid)")
        } else {
            let seconds = Double(args[4])!
            let rc = SCRecordingOutputConfiguration()
            rc.outputURL = URL(fileURLWithPath: path)
            rc.videoCodecType = .h264
            rc.outputFileType = .mp4
            let delegate = RecordingDelegate()
            let output = SCRecordingOutput(configuration: rc, delegate: delegate)
            let stream = SCStream(filter: filter, configuration: config, delegate: nil)
            try stream.addRecordingOutput(output)
            try await stream.startCapture()
            try await Task.sleep(for: .seconds(seconds))
            try await stream.stopCapture()
            for _ in 0..<100 {
                if delegate.finished { break }
                try await Task.sleep(for: .milliseconds(100))
            }
            if let error = delegate.error { throw error }
            guard delegate.finished else { fatalError("Recording did not finalize") }
            print("FINISHED \(CMTimeGetSeconds(output.recordedDuration)) seconds")
        }
    }
}

import AppKit
// A native vector drawing, generated on the build machine; no external assets.
let edge = 1024
guard CommandLine.arguments.count == 2,
      let image = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: edge, pixelsHigh: edge, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
      let context = NSGraphicsContext(bitmapImageRep: image) else { fatalError("Cannot create icon") }
NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = context
NSColor(calibratedRed: 0.035, green: 0.08, blue: 0.12, alpha: 1).setFill()
NSBezierPath(rect: NSRect(x: 0, y: 0, width: CGFloat(edge), height: CGFloat(edge))).fill()
NSColor(calibratedRed: 0.29, green: 0.9, blue: 0.67, alpha: 1).setStroke()
func arrow(_ points: [NSPoint]) { let path = NSBezierPath(); path.lineWidth = 62; path.lineCapStyle = .round; path.lineJoinStyle = .round; path.move(to: points[0]); for p in points.dropFirst() { path.line(to: p) }; path.stroke() }
arrow([NSPoint(x: 250, y: 590), NSPoint(x: 360, y: 720), NSPoint(x: 750, y: 720)])
arrow([NSPoint(x: 640, y: 830), NSPoint(x: 750, y: 720), NSPoint(x: 640, y: 610)])
arrow([NSPoint(x: 774, y: 434), NSPoint(x: 664, y: 304), NSPoint(x: 274, y: 304)])
arrow([NSPoint(x: 384, y: 414), NSPoint(x: 274, y: 304), NSPoint(x: 384, y: 194)])
NSGraphicsContext.restoreGraphicsState()
guard let png = image.representation(using: .png, properties: [:]) else { fatalError("Cannot encode icon") }
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))

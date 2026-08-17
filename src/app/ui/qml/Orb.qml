import QtQuick 2.15

// Layered procedural crimson intelligence core. It stays sharp at every size.
Item {
    id: orb
    property string state: "idle"
    property real energy: 0.0
    property int particleCount: 64
    property int fpsIdle: 24
    property int fpsActive: 36
    property bool focused: true
    property real phase: 0
    readonly property bool active: state === "listening" || state === "thinking" || state === "speaking" || state === "executing"
    readonly property real intensity: Math.min(1, 0.22 + energy * 0.62 + (active ? 0.18 : 0))

    Canvas {
        id: art
        anchors.fill: parent
        antialiasing: true
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var w = width, h = height, cx = w / 2, cy = h / 2
            var R = Math.min(w, h) * 0.43, p = orb.phase, hot = orb.intensity
            var bloom = ctx.createRadialGradient(cx, cy, R * 0.03, cx, cy, R * 1.28)
            bloom.addColorStop(0, "rgba(255,108,120," + (0.45 + hot * 0.25) + ")")
            bloom.addColorStop(0.12, "rgba(224,30,54," + (0.32 + hot * 0.18) + ")")
            bloom.addColorStop(0.48, "rgba(132,7,24," + (0.22 + hot * 0.12) + ")")
            bloom.addColorStop(1, "rgba(30,0,5,0)")
            ctx.fillStyle = bloom; ctx.fillRect(0, 0, w, h)

            // Shield rings and fine globe structure.
            for (var shield = 0; shield < 3; shield++) {
                var sr = R * (0.82 + shield * 0.14), sa = p * (shield % 2 ? -0.10 : 0.07) + shield
                ctx.beginPath(); ctx.arc(cx, cy, sr, sa, sa + 4.4)
                ctx.strokeStyle = "rgba(160,24,42," + (0.13 + shield * 0.03) + ")"; ctx.lineWidth = 1; ctx.stroke()
            }
            ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.26)
            for (var lat = -3; lat <= 3; lat++) {
                ctx.beginPath(); ctx.ellipse(0, lat * R * 0.18, R * 0.78, R * (0.18 + Math.abs(lat) * 0.028), 0, 0, Math.PI * 2)
                ctx.strokeStyle = "rgba(238,52,70," + (0.06 + hot * 0.05) + ")"; ctx.lineWidth = 0.7; ctx.stroke()
            }
            for (var lng = 0; lng < 8; lng++) {
                ctx.beginPath(); ctx.ellipse(0, 0, R * (0.18 + (lng % 4) * 0.16), R * 0.78, 0, 0, Math.PI * 2)
                ctx.strokeStyle = "rgba(255,72,88,0.08)"; ctx.lineWidth = 0.7; ctx.stroke()
            }
            ctx.restore()

            // Different moving orbital traces.
            for (var ring = 0; ring < 3; ring++) {
                var rr = R * (0.36 + ring * 0.17), start = p * (0.42 + ring * 0.12) + ring * 2.1
                ctx.beginPath(); ctx.arc(cx, cy, rr, start, start + 1.5 + hot * 0.65)
                ctx.strokeStyle = ring === 1 ? "rgba(255,106,117," + (0.55 + hot * 0.3) + ")" : "rgba(213,28,52," + (0.45 + hot * 0.3) + ")"
                ctx.lineWidth = ring === 1 ? 2.4 : 1.25; ctx.shadowBlur = 12; ctx.shadowColor = "#e5213d"; ctx.stroke(); ctx.shadowBlur = 0
            }

            // Deterministic data sparks and their faint links.
            for (var i = 0; i < particleCount; i++) {
                var a = i * 2.39996 + p * (0.17 + (i % 5) * 0.018)
                var rad = R * (0.61 + 0.30 * Math.sin(i * 1.71 + p * 0.9))
                var x = cx + Math.cos(a) * rad, y = cy + Math.sin(a) * rad * 0.72
                var size = 0.7 + (i % 4) * 0.45 + hot * 0.65
                ctx.fillStyle = (i % 7 === 0) ? "rgba(255,190,193," + (0.45 + hot * 0.4) + ")" : "rgba(237,45,64," + (0.32 + hot * 0.38) + ")"
                ctx.fillRect(x - size / 2, y - size / 2, size, size)
                if (i % 6 === 0) { ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * R * 0.16, cy + Math.sin(a) * R * 0.12); ctx.lineTo(x, y); ctx.strokeStyle = "rgba(224,38,57,0.16)"; ctx.lineWidth = 0.6; ctx.stroke() }
            }

            var core = ctx.createRadialGradient(cx - R * 0.08, cy - R * 0.08, 0, cx, cy, R * 0.32)
            core.addColorStop(0, "rgba(255,239,241," + (0.82 + hot * 0.15) + ")")
            core.addColorStop(0.17, "rgba(255,101,113," + (0.88 + hot * 0.1) + ")")
            core.addColorStop(0.55, "rgba(203,20,44," + (0.85 + hot * 0.1) + ")")
            core.addColorStop(1, "rgba(66,3,14,0.15)")
            ctx.beginPath(); ctx.arc(cx, cy, R * (0.21 + hot * 0.035), 0, Math.PI * 2); ctx.fillStyle = core; ctx.shadowBlur = 26; ctx.shadowColor = "#f32d47"; ctx.fill(); ctx.shadowBlur = 0
            ctx.strokeStyle = "rgba(255,211,215,0.72)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, R * 0.09, 0, Math.PI * 2); ctx.stroke()
            for (var tick = 0; tick < 4; tick++) { var ta = tick * Math.PI / 2 + p * 0.12; ctx.beginPath(); ctx.moveTo(cx + Math.cos(ta) * R * 0.25, cy + Math.sin(ta) * R * 0.25); ctx.lineTo(cx + Math.cos(ta) * R * 0.31, cy + Math.sin(ta) * R * 0.31); ctx.stroke() }
        }
    }

    Text { anchors.centerIn: parent; text: "A"; color: "#fff1f2"; opacity: 0.84; font { family: "Consolas"; pixelSize: Math.max(18, parent.width * 0.10); bold: true; letterSpacing: 4 } }
    Timer { interval: orb.active ? Math.max(24, 1000 / orb.fpsActive) : Math.max(40, 1000 / orb.fpsIdle); running: true; repeat: true; onTriggered: { orb.phase += orb.active ? 0.085 : 0.028; art.requestPaint() } }
    Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
    onStateChanged: scale = state === "listening" || state === "speaking" ? 1.055 : state === "thinking" ? 1.025 : 1.0
    onEnergyChanged: art.requestPaint()
}

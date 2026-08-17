import QtQuick 2.15

// Intentionally lightweight: static violet HUD geometry plus one calm pulse.
// No Canvas redraw loop, particles, or rotating effects.
Item {
    id: orb
    property string state: "idle"
    property real energy: 0.0
    property int particleCount: 64
    property int fpsIdle: 24
    property int fpsActive: 36
    property bool focused: true
    readonly property bool engaged: state === "listening" || state === "thinking" || state === "speaking" || state === "executing"

    Item {
        id: coreGroup
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height)
        height: width

        Rectangle { anchors.centerIn: parent; width: parent.width * 0.96; height: width; radius: width / 2; color: "transparent"; border.color: "#2a1748"; border.width: 1 }
        Rectangle { anchors.centerIn: parent; width: parent.width * 0.78; height: width; radius: width / 2; color: "#100a1d"; border.color: "#583a86"; border.width: 1; opacity: 0.82 }
        Rectangle { anchors.centerIn: parent; width: parent.width * 0.61; height: width; radius: width / 2; color: "#1c1035"; border.color: "#8d63d6"; border.width: 1; opacity: 0.88 }
        Rectangle { anchors.centerIn: parent; width: parent.width * 0.38; height: width; radius: width / 2; color: "#502c87"; border.color: "#c9aeff"; border.width: 2 }
        Rectangle { anchors.centerIn: parent; width: parent.width * 0.18; height: width; radius: width / 2; color: "#eee6ff"; opacity: 0.92 }

        // Reticle lines retain the technical / Jarvis-style essence at no animation cost.
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.86; height: 1; color: "#7752ad"; opacity: 0.5 }
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter; width: 1; height: parent.height * 0.86; color: "#7752ad"; opacity: 0.5 }
        Repeater {
            model: 8
            delegate: Rectangle {
                required property int index
                width: 7; height: 2; color: "#c9aeff"; opacity: 0.8
                x: coreGroup.width / 2 + Math.cos(index * Math.PI / 4) * coreGroup.width * 0.46 - width / 2
                y: coreGroup.height / 2 + Math.sin(index * Math.PI / 4) * coreGroup.height * 0.46 - height / 2
            }
        }
        Text { anchors.centerIn: parent; text: "A"; color: "#291347"; font { family: "Consolas"; pixelSize: Math.max(18, parent.width * 0.10); bold: true; letterSpacing: 4 } }

        SequentialAnimation on scale {
            running: orb.focused
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: orb.engaged ? 1.035 : 1.018; duration: orb.engaged ? 900 : 2600; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0; duration: orb.engaged ? 900 : 2600; easing.type: Easing.InOutSine }
            PauseAnimation { duration: orb.engaged ? 400 : 1800 }
        }
    }

    Text {
        anchors { horizontalCenter: parent.horizontalCenter; top: coreGroup.bottom; topMargin: 12 }
        text: state.toUpperCase() + " // CORE LINK"
        color: "#9b7bcf"
        font { family: "Consolas"; pixelSize: 9; letterSpacing: 2 }
    }
}

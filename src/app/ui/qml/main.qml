import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtMultimedia 2.15

// ---------------------------------------------------------------------------
// ALANA main interface — frameless, dark, crimson holographic command space.
// ---------------------------------------------------------------------------
Window {
    id: win
    visible: true
    flags: Qt.FramelessWindowHint | Qt.Window
    width: (typeof cfg !== "undefined" && cfg.window) ? cfg.window.width : 980
    height: (typeof cfg !== "undefined" && cfg.window) ? cfg.window.height : 760
    minimumWidth: (typeof cfg !== "undefined" && cfg.window) ? cfg.window.minWidth : 760
    minimumHeight: (typeof cfg !== "undefined" && cfg.window) ? cfg.window.minHeight : 560
    color: palette.background
    title: "ALANA"

    property string stateLabel: alana ? alana.orbState : "idle"
    property real orbFrac: 0.82
    property bool isMini: alana ? alana.mini : false

    // -- whole-window drag (underneath every interactive element) --------------
    MouseArea {
        id: windowDrag
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        drag.target: win
        drag.minimumX: 0
        drag.minimumY: 0
        drag.maximumX: 2000
        drag.maximumY: 1200
    }

    // ===========================================================================
    // TOP BAR
    // ===========================================================================
        Item {
        id: titleBar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 64
        z: 2

        Column {
            anchors { left: parent.left; leftMargin: 26; verticalCenter: parent.verticalCenter }
            spacing: 1
            Text {
                text: "ALANA"
                color: palette.core
                font { family: "Consolas"; pixelSize: 20; letterSpacing: 6 }
            }
            Text {
                text: "CORE // v1.0"
                color: palette.hudText
                font { family: "Consolas"; pixelSize: 9; letterSpacing: 3 }
            }
        }

        Row {
            anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
            spacing: 6

Rectangle {
                width: 40; height: 28; radius: 2
                color: alana && alana.spotifyVisible ? palette.wine : "transparent"
                border.color: alana && alana.spotifyVisible ? palette.accent : palette.hudLine
                Text {
                    anchors.centerIn: parent
                    text: "\u266A"
                    color: alana && alana.spotifyVisible ? palette.core : palette.hudText
                    font.pixelSize: 14
                }
                MouseArea { anchors.fill: parent; onClicked: alana.spotifyTogglePanel() }
            }
            Rectangle {
                width: 34; height: 28; radius: 2
                color: alana && alana.mini ? palette.wine : "transparent"
                border.color: alana && alana.mini ? palette.accent : palette.hudLine
                Text {
                    anchors.centerIn: parent
                    text: "\u25F1"
                    color: alana && alana.mini ? palette.core : palette.hudText
                    font.pixelSize: 13
                }
                MouseArea { anchors.fill: parent; onClicked: alana.setMini(!alana.mini) }
            }
            Rectangle {
                width: 34; height: 28; radius: 2
                color: "transparent"
                border.color: palette.hudLine
                Text {
                    anchors.centerIn: parent
                    text: "\u2013"
                    color: palette.hudText
                    font.pixelSize: 14
                }
                MouseArea { anchors.fill: parent; onClicked: win.showMinimized() }
            }
            Rectangle {
                width: 34; height: 28; radius: 2
                color: "transparent"
                border.color: palette.hudLine
                Text {
                    anchors.centerIn: parent
                    text: "\u00D7"
                    color: palette.accent
                    font.pixelSize: 15
                }
                MouseArea { anchors.fill: parent; onClicked: alana.quit() }
            }
        }
    }
// ===========================================================================
    // HUD — sparse framing, never competes with the orb
    // ===========================================================================
        Item {
        id: hud
        anchors.fill: parent
        anchors { leftMargin: 18; rightMargin: 18; topMargin: 74; bottomMargin: 158 }
        z: 1

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1; color: palette.hudLine; opacity: 0.7
        }
        Rectangle { color: palette.hudLine; x: 0; y: 0; width: 22; height: 1 }
        Rectangle { color: palette.hudLine; x: 0; y: 0; width: 1; height: 22 }
        Rectangle { color: palette.hudLine; x: parent.width - 22; y: 0; width: 22; height: 1 }
        Rectangle { color: palette.hudLine; x: parent.width - 1; y: 0; width: 1; height: 22 }
        Rectangle { color: palette.hudLine; x: parent.width - 22; y: parent.height - 1; width: 22; height: 1 }
        Rectangle { color: palette.hudLine; x: parent.width - 1; y: parent.height - 22; width: 1; height: 22 }
        Rectangle { color: palette.hudLine; x: 0; y: parent.height - 1; width: 22; height: 1 }
        Rectangle { color: palette.hudLine; x: 0; y: parent.height - 22; width: 1; height: 22 }

        Rectangle { color: palette.hudLine; opacity: 0.5; x: parent.width * 0.52; y: 28; width: 1; height: parent.height - 56 }

        Column {
            anchors { top: parent.top; topMargin: 12; right: parent.right; rightMargin: 16 }
            spacing: 3
            Text { text: "SRC // LOCAL"; color: palette.hudText; font { family: "Consolas"; pixelSize: 8; letterSpacing: 2 } }
            Text { text: "PWR // STABLE"; color: palette.hudText; font { family: "Consolas"; pixelSize: 8; letterSpacing: 2 } }
        }
        Column {
            anchors { top: parent.top; topMargin: 12; left: parent.left; leftMargin: 16 }
            spacing: 3
            Text { text: "INT // HARMONIC"; color: palette.hudText; font { family: "Consolas"; pixelSize: 8; letterSpacing: 2 } }
            Text {
                text: stateLabel.toUpperCase()
                color: (stateLabel === "listening" || stateLabel === "speaking" || stateLabel === "executing" || stateLabel === "error") ? palette.core : palette.accent
                font { family: "Consolas"; pixelSize: 8; letterSpacing: 2 }
            }
        }
    }

    // ===========================================================================
    // CENTRAL ORB
    // ===========================================================================
        Item {
        id: orbFrame
        anchors { left: hud.left; top: hud.top; bottom: hud.bottom; right: hud.horizontalCenter; rightMargin: 18; topMargin: 30; bottomMargin: 30 }
        z: 1

        Orb {
            id: orb
            anchors.centerIn: parent
            width: Math.min(orbFrame.width, orbFrame.height) * orbFrac
            height: width
            state: alana ? alana.orbState : "idle"
            energy: alana ? alana.orbEnergy : 0
            particleCount: (typeof cfg !== "undefined" && cfg.orb) ? cfg.orb.particleCount : 64
            fpsIdle: (typeof cfg !== "undefined" && cfg.orb) ? cfg.orb.fpsIdle : 24
            fpsActive: (typeof cfg !== "undefined" && cfg.orb) ? cfg.orb.fpsActive : 36
            focused: win.active

            // wake indicator while voice mode is armed
            Text {
                anchors { horizontalCenter: parent.horizontalCenter; top: parent.bottom; topMargin: 8 }
                text: (alana && alana.voiceMode) ? "WAKE // ARMED" : " "
                color: palette.hudText
                font { family: "Consolas"; pixelSize: 8; letterSpacing: 3 }
                visible: alana && alana.voiceMode
            }
        }
    }

    // ===========================================================================
    // CONVERSATION DISPLAY  (TEXT / VOICE MODE)
    // ===========================================================================
    Item {
        id: chatPanel
        anchors {
            left: hud.horizontalCenter; leftMargin: 20; right: hud.right; rightMargin: 14
            bottom: inputRow.top; bottomMargin: 12
            top: titleBar.bottom; topMargin: 10
        }
        z: 1
        opacity: win.isMini ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle { anchors.fill: parent; color: "#0c0507"; border.color: palette.hudLine; border.width: 1; opacity: 0.96 }
        Rectangle {
            anchors { left: parent.left; top: parent.top; leftMargin: 16; topMargin: 14 }
            width: 46; height: 2; color: palette.accent
        }
        Text {
            anchors { left: parent.left; top: parent.top; leftMargin: 16; topMargin: 24 }
            text: "CONVERSATION // LIVE"
            color: palette.hudText
            font { family: "Consolas"; pixelSize: 9; letterSpacing: 2 }
        }

        ListModel { id: convModel }

        Connections {
            target: alana
            function onConversationAppended(msg) {
                convModel.append({"sender": msg.role || "alana", "body": msg.text || ""})
                listView.contentY = listView.contentHeight - listView.height
            }
        }

        Text {
            id: emptyHint
            anchors.centerIn: parent
            text: (alana && alana.voiceMode) ? "Listening for 'Alana'…" : "How can I help you, Sir?"
            color: palette.textDim
            font { family: "Consolas"; pixelSize: 13; letterSpacing: 2 }
            visible: convModel.count === 0
            z: 1
        }

        Flickable {
            id: listView
            anchors { fill: parent; topMargin: 54; leftMargin: 14; rightMargin: 14; bottomMargin: 12 }
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            bottomMargin: 14
            interactive: convModel.count > 0

            Text { id: spacer; width: listView.width; height: listView.contentHeight + 40 }

            Column {
                id: convRoot
                width: listView.width
                anchors.top: spacer.top
                spacing: 14

                Repeater {
                    model: convModel
                    delegate: Item {
                        width: convRoot.width
                        height: Math.min(520, bubble.implicitHeight + 48)
                        property bool isAlana: model.sender === "alana"
                        Rectangle {
                            id: bubble
                            width: Math.min(parent.width * 0.88, 460)
                            height: txt.implicitHeight + 28
                            radius: 4
                            color: isAlana ? palette.page : palette.wine
                            border.color: isAlana ? palette.hudLine : palette.accent
                            border.width: 1
                            anchors.left: isAlana ? parent.left : undefined
                            anchors.right: isAlana ? undefined : parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                id: txt
                                anchors { fill: parent; leftMargin: 16; rightMargin: 16; topMargin: 14; bottomMargin: 12 }
                                text: model.body
                                color: isAlana ? palette.textPrimary : "#f2d7da"
                                font { family: "Segoe UI"; pixelSize: 14; letterSpacing: 0.2 }
                                wrapMode: Text.Wrap
                                lineHeight: 1.35
                            }
                        }
                    }
                }
            }
        }
    }

    // ===========================================================================
    // INPUT ROW  (message field · voice/text toggle · push-to-talk · send)
    // ===========================================================================
    Item {
        id: inputRow
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 28 }
        height: 72
        z: 3
        opacity: win.isMini ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle {
            anchors.fill: parent; anchors.margins: 4; radius: 4
            color: "#100507"; border.color: palette.accent; opacity: 0.98
        }

        RowLayout {
            anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
            spacing: 10

            TextField {
                id: txtInput
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                placeholderText: alana && alana.voiceMode ? "Voice mode active…" : "Message ALANA…"
                placeholderTextColor: "#9d777c"
                color: "#fff3f4"
                selectionColor: palette.accent
                selectedTextColor: "#ffffff"
                font { family: "Segoe UI"; pixelSize: 16 }
                background: Rectangle {
                    color: "#050405"; radius: 3
                    border.color: txtInput.activeFocus ? palette.accent : palette.hudLine
                    border.width: txtInput.activeFocus ? 2 : 1; opacity: 1
                }
                onTextChanged: {
                    if (text && text.trim().length > 0) { if (alana) alana.setTyping("typing") }
                    else { if (alana) alana.setTyping("idle") }
                }
                onAccepted: {
                    if (alana && txtInput.text.trim()) {
                        alana.send(txtInput.text); txtInput.text = ""; alana.setTyping("idle")
                    }
                }
            }

            Rectangle {
                id: modeToggle
                Layout.preferredWidth: 120; Layout.preferredHeight: 48; radius: 3
                color: alana && alana.voiceMode ? palette.wine : "#111112"
                border.color: alana && alana.voiceMode ? palette.accent : palette.hudLine
                opacity: (alana && alana.voiceAvailable) ? 0.92 : 0.45
                Text {
                    anchors.centerIn: parent
                    text: (alana && alana.voiceMode) ? "[TEXT]" : "[VOICE]"
                    color: alana && alana.voiceMode ? palette.core : palette.hudText
                    font { family: "Consolas"; pixelSize: 13; letterSpacing: 4 }
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: { if (alana && alana.voiceAvailable) alana.toggleVoice() }
                }
            }

            Rectangle {
                id: micBtn
                Layout.preferredWidth: 48; Layout.preferredHeight: 48; radius: 24
                color: palette.wine; border.color: palette.accent; border.width: 1
                visible: alana && alana.voiceMode
                property bool pressed: false
                opacity: pressed ? 0.55 : 0.85
                Text {
                    anchors.centerIn: parent
                    text: "\u1F3A4"; color: palette.core; font.pixelSize: 18
                    opacity: parent.pressed ? 0.6 : 1
                }
                                MouseArea {
                    anchors.fill: parent
                    onClicked: { if (alana) alana.listenPushToTalk() }
                }
            }

            Rectangle {
                id: btnSend
                Layout.preferredWidth: 52; Layout.preferredHeight: 48; radius: 3
                color: txtInput.text.trim() ? palette.accent : palette.hudLine
                opacity: txtInput.text.trim() ? 0.92 : 0.45
                Text {
                    anchors.centerIn: parent
                    text: "\u27A1"; color: palette.page; font.pixelSize: 16
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: txtInput.text.trim().length > 0
                    onClicked: {
                        if (alana && txtInput.text.trim()) {
                            alana.send(txtInput.text); txtInput.text = ""; alana.setTyping("idle")
                        }
                    }
                }
            }
        }
    }

    // ===========================================================================
    // MEDIA PLAYER (compact bar, appears at the bottom when a file is opened)
    // ===========================================================================
    Item {
        id: mediaBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 98 }
        height: 44
        z: 4
        opacity: (alana && alana.mediaOpen) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        visible: alana && alana.mediaOpen

        Rectangle {
            anchors { fill: parent; margins: 4 }
            radius: 6
            color: palette.page
            border.color: palette.accent
            opacity: 0.95

            Row {
                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                spacing: 10
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "\u266A"
                    color: palette.core
                    font.pixelSize: 16
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: alana ? alana.mediaTitle() : ""
                    color: palette.textPrimary
                    font { family: "Segoe UI"; pixelSize: 12 }
                    width: parent.width - 120
                    elide: Text.ElideRight
                }
                Item { width: 10; height: 1 }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30; height: 24; radius: 4
                    color: "transparent"
                    border.color: palette.hudLine
                    Text {
                        anchors.centerIn: parent
                        text: alana && alana.mediaPlaying ? "\u23F8" : "\u25B6"
                        color: palette.core; font.pixelSize: 12
                    }
                    MouseArea { anchors.fill: parent; onClicked: { if (alana) alana.toggleMedia() } }
                }
            }
        }
    }

    // ===========================================================================
    

    // ===========================================================================
    // SPOTIFY MUSIC PLAYER — custom theme panel (right side, toggleable)
    // ===========================================================================
    Item {
        id: spotifyPanel
        anchors {
            left: hud.horizontalCenter; leftMargin: 20
            right: hud.right; rightMargin: 14
            bottom: inputRow.top; bottomMargin: 12
            top: titleBar.bottom; topMargin: 10
        }
        z: 6
        visible: alana && alana.spotifyVisible
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle {
            anchors.fill: parent
            color: "#0c0507"
            border.color: palette.accent
            border.width: 1
            opacity: 0.97
        }

        Column {
            anchors { fill: parent; topMargin: 16; leftMargin: 22; rightMargin: 22; bottomMargin: 18 }
            spacing: 12

            Row {
                width: parent.width
                Text {
                    text: "NOW PLAYING // SPOTIFY"
                    color: palette.hudText
                    font { family: "Consolas"; pixelSize: 9; letterSpacing: 2 }
                }
                Item { width: parent.width - 270; height: 1 }
                Text {
                    text: "PLAYBACK UNIT"
                    color: palette.hudText
                    font { family: "Consolas"; pixelSize: 8; letterSpacing: 2 }
                }
            }

            Rectangle {
                id: artFrame
                width: Math.min(parent.width, parent.height * 0.52)
                height: width
                anchors.horizontalCenter: parent.horizontalCenter
                radius: 6
                color: "#1a0b1e"
                border.color: palette.hudLine
                border.width: 1
                clip: true

                Image {
                    anchors.fill: parent
                    source: alana && alana.spotifyArtwork ? alana.spotifyArtwork : ""
                    fillMode: Image.PreserveAspectCrop
                    cache: false
                }
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    border.color: palette.accent
                    border.width: alana && alana.spotifyArtwork ? 1 : 0
                    visible: alana && alana.spotifyArtwork
                }
                Text {
                    anchors.centerIn: parent
                    visible: !(alana && alana.spotifyArtwork)
                    text: "\u266A"
                    color: palette.hudText
                    font.pixelSize: 64
                }
            }

            Text {
                width: parent.width
                text: alana ? alana.spotifyTitle : ""
                color: palette.textPrimary
                font { family: "Segoe UI"; pixelSize: 17; bold: true }
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.NoWrap
            }

            Text {
                width: parent.width
                text: alana ? alana.spotifyArtist : ""
                color: palette.textDim
                font { family: "Segoe UI"; pixelSize: 13 }
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
            }

    Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 18

                Rectangle {
                    width: 44; height: 44; radius: 22
                    color: "transparent"
                    border.color: palette.hudLine
                    Text { anchors.centerIn: parent; text: "\u23EE"; color: palette.core; font.pixelSize: 16 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { if (alana) alana.spotifyPrevious() }
                    }
                }
                Rectangle {
                    width: 54; height: 54; radius: 27
                    color: palette.wine
                    border.color: palette.accent
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: alana && alana.spotifyPlaying ? "\u23F8" : "\u25B6"
                        color: palette.core
                        font.pixelSize: 20
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { if (alana) alana.spotifyToggle() }
                    }
                }
                Rectangle {
                    width: 44; height: 44; radius: 22
                    color: "transparent"
                    border.color: palette.hudLine
                    Text { anchors.centerIn: parent; text: "\u23ED"; color: palette.core; font.pixelSize: 16 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { if (alana) alana.spotifyNext() }
                    }
                }
            }

            Row {
                width: parent.width
                TextField {
                    id: spotifySearch
                    width: parent.width - 58
                    height: 38
                    placeholderText: "Search and play a song, artist, album"
                    placeholderTextColor: "#9d777c"
                    color: "#fff3f4"
                    font { family: "Segoe UI"; pixelSize: 13 }
                    background: Rectangle {
                        color: "#050405"; radius: 3
                        border.color: spotifySearch.activeFocus ? palette.accent : palette.hudLine
                    }
                    onAccepted: {
                        if (alana && text.trim()) { alana.spotifySearch(text); text = "" }
                    }
                }
                Rectangle {
                    width: 48; height: 38; radius: 3
                    color: palette.accent; opacity: 0.92
                    Text { anchors.centerIn: parent; text: "\u27A1"; color: palette.page; font.pixelSize: 15 }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if (alana && spotifySearch.text.trim()) {
                                alana.spotifySearch(spotifySearch.text); spotifySearch.text = ""
                            }
                        }
                    }
                }
            }
        }
    }

    // ===========================================================================
    // EMAIL CONFIRMATION  (show before any email is actually sent)
    // ===========================================================================
    Item {
        id: emailConfirmOverlay
        anchors.fill: parent
        z: 20
        visible: alana && alana.emailPending
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 150 } }

        MouseArea { anchors.fill: parent; acceptedButtons: Qt.NoButton }

        Rectangle {
            anchors.fill: parent
            color: "#000000"
            opacity: 0.6
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(520, parent.width - 60)
            height: 360
            radius: 8
            color: palette.page
            border.color: palette.accent
            border.width: 2

            Column {
                anchors { fill: parent; topMargin: 22; leftMargin: 24; rightMargin: 24; bottomMargin: 20 }
                spacing: 12

                Text {
                    text: "EMAIL CONFIRMATION"
                    color: palette.core
                    font { family: "Consolas"; pixelSize: 12; letterSpacing: 3 }
                }
                Text {
                    text: "To: " + (alana ? alana.emailRecipient : "")
                    color: palette.textPrimary
                    font { family: "Segoe UI"; pixelSize: 13 }
                }
                Text {
                    text: "Subject: " + (alana ? alana.emailSubject : "")
                    color: palette.textPrimary
                    font { family: "Segoe UI"; pixelSize: 13 }
                }
                Rectangle { width: parent.width; height: 1; color: palette.hudLine }

                Flickable {
                    width: parent.width
                    height: 140
                    clip: true
                    Text {
                        width: parent.width
                        text: alana ? alana.emailBody : ""
                        color: palette.textDim
                        font { family: "Segoe UI"; pixelSize: 12 }
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }

                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 16
                    Rectangle {
                        width: 150; height: 42; radius: 4
                        color: palette.accent
                        Text { anchors.centerIn: parent; text: "SEND"; color: palette.page; font { family: "Consolas"; pixelSize: 12; letterSpacing: 3 } }
                        MouseArea { anchors.fill: parent; onClicked: { if (alana) alana.confirmEmailSend() } }
                    }
                    Rectangle {
                        width: 150; height: 42; radius: 4
                        color: "transparent"
                        border.color: palette.hudLine
                        Text { anchors.centerIn: parent; text: "CANCEL"; color: palette.hudText; font { family: "Consolas"; pixelSize: 12; letterSpacing: 3 } }
                        MouseArea { anchors.fill: parent; onClicked: { if (alana) alana.cancelEmailSend() } }
                    }
                }
            }
        }
    }

    // MINI MODE — compact orb-only floating widget (toggled from title bar)
    // ===========================================================================
    Item {
        id: miniOverlay
        anchors.fill: parent
        z: 5
        visible: win.isMini
        opacity: win.isMini ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }

        MouseArea {
            anchors.fill: parent
            drag.target: win
            drag.minimumX: 0; drag.minimumY: 0
            drag.maximumX: 3000; drag.maximumY: 2000
        }

        Orb {
            anchors.centerIn: parent
            width: Math.min(win.width, win.height) * 0.8
            height: width
            state: alana ? alana.orbState : "idle"
            energy: alana ? alana.orbEnergy : 0
            particleCount: 48
            fpsIdle: 18
            fpsActive: 30
            focused: win.active
        }

        Text {
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 24 }
            text: stateLabel.toUpperCase()
            color: (stateLabel === "listening" || stateLabel === "speaking" || stateLabel === "executing") ? palette.core : palette.accent
            font { family: "Consolas"; pixelSize: 10; letterSpacing: 3 }
        }

        Rectangle {
            anchors { top: parent.top; topMargin: 10; right: parent.right; rightMargin: 10 }
            width: 30; height: 24; radius: 2
            color: "transparent"
            border.color: palette.hudLine
            Text { anchors.centerIn: parent; text: "\u25F1"; color: palette.hudText; font.pixelSize: 10 }
            MouseArea { anchors.fill: parent; onClicked: { if (alana) alana.setMini(false) } }
        }
    }
}

// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
// ShowRoom's preferences: a floating window with the sections on the right,
// driven by "bridge" (dtpanels/prefs_window.py). QtQuick core only.
import QtQuick

Rectangle {
    id: root
    property var th: bridge.theme
    property real s: th.s
    property string query: search.text
    property bool searching: query.trim().length > 0
    color: th.window
    border.color: th.line
    border.width: 1
    radius: Math.round(14 * s)

    function focusSearch() { search.forceActiveFocus(); search.selectAll() }
    function sectionOf(title) {
        for (var i = 0; i < bridge.sections.length; ++i)
            if (bridge.sections[i].title === title) return bridge.sections[i]
        return null
    }
    function changedIn(sec) {           // how many settings of a section differ from the default
        var n = 0, v = bridge.values
        for (var i = 0; i < sec.params.length; ++i) {
            var p = sec.params[i]
            if (p.hasDefault && String(v[p.name]) !== String(p["default"])) n++
        }
        return n
    }
    function matchesIn(sec) {
        var n = 0, h = bridge.hidden
        for (var i = 0; i < sec.params.length; ++i) if (h.indexOf(sec.params[i].name) < 0) n++
        return n
    }
    property int currentIndex: {
        for (var i = 0; i < bridge.sections.length; ++i) if (bridge.sections[i].title === bridge.current) return i
        return 0
    }
    property var curSection: bridge.sections.length ? bridge.sections[currentIndex] : null

    // ---------------------------------------------------------------- title bar
    Item {
        id: titleBar
        width: parent.width; height: Math.round(46 * s)
        MouseArea {
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point start
            onPressed: function(m) { start = Qt.point(m.x, m.y) }
            onPositionChanged: function(m) { if (pressed) bridge.moveBy(m.x - start.x, m.y - start.y) }
        }
        Canvas {        // gear
            id: gear
            x: Math.round(18 * s); anchors.verticalCenter: parent.verticalCenter
            width: Math.round(24 * s); height: width
            property color c: th.accent
            onPaint: {
                var g = getContext("2d"), w = width, k = w / 24
                g.reset(); g.strokeStyle = c; g.lineWidth = 1.8 * k; g.lineCap = "round"
                g.beginPath(); g.arc(12 * k, 12 * k, 3.2 * k, 0, 2 * Math.PI); g.stroke()
                for (var a = 0; a < 8; ++a) {
                    var t = a * Math.PI / 4
                    g.beginPath(); g.moveTo((12 + 6 * Math.cos(t)) * k, (12 + 6 * Math.sin(t)) * k)
                    g.lineTo((12 + 9.5 * Math.cos(t)) * k, (12 + 9.5 * Math.sin(t)) * k); g.stroke()
                }
            }
            RotationAnimation on rotation { running: bridge.pending > 0; loops: Animation.Infinite; from: 0; to: 360; duration: 6000 }
        }
        Column {
            anchors.left: gear.right; anchors.leftMargin: Math.round(12 * s)
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "ShowRoom preferences"; color: th.text; font.pixelSize: Math.round(13 * s); font.bold: true; font.family: th.family }
            Text { text: "Saved for every document · Esc closes"; color: th.muted; font.pixelSize: Math.round(10 * s); font.family: th.family }
        }
        Rectangle {     // search
            id: searchBox
            anchors.right: closeBtn.left; anchors.rightMargin: Math.round(10 * s)
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(220 * s); height: Math.round(28 * s); radius: Math.round(8 * s)
            color: th.field
            border.width: search.activeFocus ? 1 : 0; border.color: th.accent
            Rectangle {     // focus halo
                anchors.fill: parent; anchors.margins: -Math.round(4 * s); radius: parent.radius + Math.round(4 * s)
                color: "transparent"; border.width: Math.round(4 * s)
                border.color: Qt.rgba(Qt.color(th.accent).r, Qt.color(th.accent).g, Qt.color(th.accent).b, 0.18)
                opacity: search.activeFocus ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 160 } }
            }
            Text { x: Math.round(10 * s); anchors.verticalCenter: parent.verticalCenter; text: "⌕"; color: th.muted; font.pixelSize: Math.round(15 * s) }
            TextInput {
                id: search
                anchors.fill: parent; anchors.leftMargin: Math.round(30 * s); anchors.rightMargin: Math.round(56 * s)
                verticalAlignment: TextInput.AlignVCenter
                color: th.text; selectionColor: th.accent; selectByMouse: true; clip: true
                font.pixelSize: Math.round(13 * s); font.family: th.family
                onTextChanged: bridge.setFilter(text)
                Keys.onEscapePressed: text = ""
                Text { anchors.verticalCenter: parent.verticalCenter; visible: !search.text.length; text: "Search every setting"; color: th.muted; font.pixelSize: Math.round(13 * s); font.family: th.family }
            }
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: Math.round(8 * s); anchors.verticalCenter: parent.verticalCenter
                width: kb.implicitWidth + Math.round(10 * s); height: Math.round(20 * s); radius: Math.round(5 * s)
                color: th.card
                Text { id: kb; anchors.centerIn: parent; text: "Ctrl F"; color: th.muted; font.pixelSize: Math.round(10 * s); font.family: th.family }
            }
        }
        Rectangle {
            id: closeBtn
            anchors.right: parent.right; anchors.rightMargin: Math.round(14 * s); anchors.verticalCenter: parent.verticalCenter
            width: Math.round(32 * s); height: width; radius: Math.round(8 * s)
            color: closeMa.containsMouse ? th.field : "transparent"
            Text { anchors.centerIn: parent; text: "✕"; color: th.muted; font.pixelSize: Math.round(15 * s) }
            MouseArea { id: closeMa; anchors.fill: parent; hoverEnabled: true; onClicked: bridge.cancel() }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: th.line; opacity: 0.6 }
    }

    // ---------------------------------------------------------------- footer
    Item {
        id: footer
        anchors.bottom: parent.bottom
        width: parent.width; height: Math.round(48 * s)
        Rectangle { width: parent.width; height: 1; color: th.line; opacity: 0.6 }
        Rectangle {     // unsaved changes
            id: pill
            x: Math.round(20 * s); anchors.verticalCenter: parent.verticalCenter
            height: Math.round(30 * s); radius: height / 2
            width: pillText.implicitWidth + Math.round(24 * s)
            color: Qt.rgba(Qt.color(th.accent).r, Qt.color(th.accent).g, Qt.color(th.accent).b, 0.14)
            opacity: bridge.pending > 0 ? 1 : 0
            scale: bridge.pending > 0 ? 1 : 0.85
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }
            Text { id: pillText; anchors.centerIn: parent; text: bridge.pending + (bridge.pending === 1 ? " change" : " changes") + " not applied"; color: th.accent; font.pixelSize: Math.round(12 * s); font.bold: true; font.family: th.family }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: Math.round(20 * s); anchors.verticalCenter: parent.verticalCenter
            spacing: Math.round(8 * s)
            PillButton { th: root.th; label: "Reset section"; visible: !root.searching; onClicked: bridge.resetSection(bridge.current) }
            PillButton { th: root.th; label: "Cancel"; onClicked: bridge.cancel() }
            PillButton { th: root.th; label: "Apply"; onClicked: bridge.apply() }
            PillButton { th: root.th; label: "OK"; primary: true; onClicked: bridge.ok() }
        }
    }

    // ---------------------------------------------------------------- sections, on the right
    Rectangle {
        id: side
        anchors.right: parent.right; anchors.top: titleBar.bottom; anchors.bottom: footer.top
        anchors.rightMargin: 1
        width: Math.round(204 * s)
        color: th.card
        Rectangle { width: 1; height: parent.height; color: th.line; opacity: 0.6 }
        Rectangle {     // sliding highlight
            x: Math.round(10 * s); width: parent.width - Math.round(20 * s)
            height: Math.round(32 * s); radius: Math.round(8 * s)
            y: Math.round(10 * s) + root.currentIndex * Math.round(34 * s)
            color: th.window
            border.color: th.line; border.width: 1
            opacity: root.searching ? 0 : 1
            Behavior on y { SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.25 } }
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Rectangle { x: 0; anchors.verticalCenter: parent.verticalCenter; width: Math.round(3 * s); height: parent.height * 0.5; radius: width / 2; color: th.accent }
        }
        Column {
            y: Math.round(10 * s)
            x: Math.round(10 * s); width: parent.width - Math.round(20 * s)
            spacing: Math.round(2 * s)
            Repeater {
                model: bridge.sections
                Item {
                    width: parent.width; height: Math.round(32 * s)
                    property bool cur: !root.searching && modelData.title === bridge.current
                    property int badge: root.searching ? root.matchesIn(modelData) : root.changedIn(modelData)
                    opacity: root.searching && badge === 0 ? 0.35 : 1
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                    Image {
                        id: ic
                        x: Math.round(12 * s); anchors.verticalCenter: parent.verticalCenter
                        width: Math.round(16 * s); height: width
                        source: bridge.icons[modelData.title] ? (cur ? bridge.icons[modelData.title].active : bridge.icons[modelData.title].normal) : ""
                    }
                    Text {
                        anchors.left: ic.right; anchors.leftMargin: Math.round(10 * s)
                        anchors.right: bdg.left; anchors.rightMargin: Math.round(6 * s)
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.title; elide: Text.ElideRight
                        color: cur ? th.accent : th.text
                        font.pixelSize: Math.round(12 * s); font.family: th.family; font.bold: cur
                    }
                    Rectangle {
                        id: bdg
                        anchors.right: parent.right; anchors.rightMargin: Math.round(8 * s); anchors.verticalCenter: parent.verticalCenter
                        visible: parent.badge > 0
                        width: Math.max(height, bt.implicitWidth + Math.round(10 * s)); height: Math.round(20 * s); radius: height / 2
                        color: root.searching ? th.muted : th.accent
                        Text { id: bt; anchors.centerIn: parent; text: parent.parent.badge; color: "white"; font.pixelSize: Math.round(11 * s); font.bold: true; font.family: th.family }
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { search.text = ""; bridge.select(modelData.title); flick.contentY = 0 } }
                }
            }
        }
    }

    // ---------------------------------------------------------------- content
    Flickable {
        id: flick
        anchors.left: parent.left; anchors.right: side.left; anchors.top: titleBar.bottom; anchors.bottom: footer.top
        anchors.margins: 1
        clip: true
        contentHeight: page.implicitHeight + Math.round(40 * s)
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: page
            x: Math.round(16 * s); y: Math.round(14 * s)
            width: flick.width - Math.round(32 * s)
            spacing: Math.round(12 * s)

            Row {       // page title
                spacing: Math.round(12 * s)
                Text { text: root.searching ? "Results" : bridge.current; color: th.text; font.pixelSize: Math.round(17 * s); font.bold: true; font.family: th.family }
                Text { y: Math.round(5 * s); text: root.searching ? "in every section" : (bridge.hints[bridge.current] || ""); color: th.muted; font.pixelSize: Math.round(12 * s); font.family: th.family }
            }

            // live preview of the default scene
            Rectangle {
                visible: !root.searching && bridge.current === "Default scene"
                width: parent.width; height: Math.round(120 * s); radius: Math.round(10 * s)
                color: th.card
                Rectangle {
                    id: stage
                    x: Math.round(14 * s); anchors.verticalCenter: parent.verticalCenter
                    width: Math.round(170 * s); height: Math.round(96 * s); radius: Math.round(8 * s)
                    color: th.field; clip: true
                    Canvas {        // ground grid
                        anchors.fill: parent
                        property color c: th.line
                        onPaint: {
                            var g = getContext("2d"); g.reset(); g.strokeStyle = c; g.globalAlpha = 0.6; g.lineWidth = 1
                            for (var x = 0; x < width; x += 22) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, height); g.stroke() }
                            for (var y = 0; y < height; y += 22) { g.beginPath(); g.moveTo(0, y); g.lineTo(width, y); g.stroke() }
                        }
                    }
                    property real dark: bridge.values.DefShadows ? (bridge.values.DefShadowDarkness || 0) : 0
                    property real soft: bridge.values.DefShadowSoftness || 0
                    Repeater {      // the shadow: stacked rounded layers make the blur
                        model: 7
                        Rectangle {
                            property real k: index / 6
                            x: cube.x + Math.round(16 * s) - k * stage.soft * 22 * s
                            y: cube.y + Math.round(20 * s) - k * stage.soft * 22 * s
                            width: cube.width + 2 * k * stage.soft * 22 * s
                            height: cube.height + 2 * k * stage.soft * 22 * s
                            radius: Math.round(8 * s) + k * stage.soft * 22 * s
                            color: "black"
                            opacity: stage.dark * 0.55 / 7 * (1.6 - k)
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                        }
                    }
                    Rectangle {
                        id: cube
                        x: Math.round(56 * s); y: Math.round(18 * s)
                        width: Math.round(56 * s); height: Math.round(50 * s); radius: Math.round(8 * s)
                        color: "#8fa8c8"
                        Rectangle {     // ambient occlusion settling at the bottom
                            anchors.fill: parent; radius: parent.radius
                            opacity: bridge.values.DefAO ? Math.min(1, (bridge.values.DefAOIntensity || 0) * 0.5) : 0
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                            gradient: Gradient {
                                GradientStop { position: 0.45; color: "transparent" }
                                GradientStop { position: 1.0; color: Qt.rgba(0.08, 0.12, 0.2, 0.55) }
                            }
                        }
                    }
                }
                Column {
                    anchors.left: stage.right; anchors.leftMargin: Math.round(16 * s); anchors.right: parent.right; anchors.rightMargin: Math.round(14 * s)
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Math.round(4 * s)
                    Text { text: "Live preview"; color: th.text; font.pixelSize: Math.round(13 * s); font.bold: true; font.family: th.family }
                    Text { width: parent.width; wrapMode: Text.WordWrap; text: "Follows the settings below: the shadow darkens and softens, the occlusion settles at the bottom. Nothing is saved until Apply."; color: th.muted; font.pixelSize: Math.round(11.5 * s); font.family: th.family }
                }
            }

            // the animation curve, moving
            Rectangle {
                visible: !root.searching && bridge.current === "Properties panel"
                width: parent.width; height: Math.round(64 * s); radius: Math.round(12 * s)
                color: th.card
                Text { x: Math.round(14 * s); y: Math.round(10 * s); text: "Animation: " + (bridge.values.PanelEasing || "") + ", " + (bridge.values.PanelAnimMs || 0) + " ms"; color: th.muted; font.pixelSize: Math.round(11.5 * s); font.family: th.family }
                Rectangle {
                    id: lane
                    x: Math.round(14 * s); y: Math.round(32 * s)
                    width: parent.width - Math.round(28 * s); height: Math.round(18 * s); radius: height / 2
                    color: th.field
                    Rectangle {
                        id: runner
                        y: Math.round(3 * s); height: parent.height - Math.round(6 * s); width: Math.round(70 * s); radius: height / 2
                        color: th.accent
                        SequentialAnimation on x {
                            running: lane.visible; loops: Animation.Infinite
                            PauseAnimation { duration: 350 }
                            NumberAnimation { from: Math.round(3 * s); to: lane.width - runner.width - Math.round(3 * s)
                                duration: Math.max(120, (bridge.values.PanelAnimMs || 200) * 3)
                                easing.type: Easing[bridge.values.PanelEasing] !== undefined ? Easing[bridge.values.PanelEasing] : Easing.OutQuart }
                            PauseAnimation { duration: 350 }
                            NumberAnimation { to: Math.round(3 * s); from: lane.width - runner.width - Math.round(3 * s)
                                duration: Math.max(120, (bridge.values.PanelAnimMs || 200) * 3)
                                easing.type: Easing[bridge.values.PanelEasing] !== undefined ? Easing[bridge.values.PanelEasing] : Easing.OutQuart }
                        }
                    }
                }
            }

            // the settings
            Repeater {
                model: bridge.sections
                Item {
                    width: page.width
                    property bool shown: root.searching ? root.matchesIn(modelData) > 0 : modelData.title === bridge.current
                    visible: shown
                    height: shown ? sec.height + (root.searching ? cap.height + Math.round(4 * s) : 0) : 0
                    Text { id: cap; visible: root.searching; text: modelData.title; color: th.muted; font.pixelSize: Math.round(11 * s); font.bold: true; font.family: th.family }
                    Section {
                        id: sec
                        y: root.searching ? cap.height + Math.round(4 * s) : 0
                        th: root.th; section: modelData; width: parent.width
                        opacity: parent.shown ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 220 } }
                    }
                }
            }

            // actions (Maintenance)
            Flow {
                visible: !root.searching && bridge.current === "Maintenance"
                width: parent.width; spacing: Math.round(8 * s)
                Repeater {
                    model: bridge.actions
                    PillButton { th: root.th; label: modelData.label; onClicked: bridge.trigger(modelData.name) }
                }
            }

            Text {
                visible: root.searching && bridge.hidden.length >= 0 && !hasAny()
                function hasAny() { for (var i = 0; i < bridge.sections.length; ++i) if (root.matchesIn(bridge.sections[i]) > 0) return true; return false }
                text: "No setting matches “" + root.query + "”."
                color: th.muted; font.pixelSize: Math.round(13 * s); font.family: th.family
            }
        }
    }
}

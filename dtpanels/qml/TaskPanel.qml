// SPDX-License-Identifier: LGPL-2.1-or-later
// Copyright (c) 2025-2026 OficineRobotica
// Generic task panel, shared with the Plastic add-on. Everything is driven by the
// "bridge" context object (see dtpanels/bridge.py). Only the QtQuick core module is required.
import QtQuick

Item {
    id: root
    property var th: bridge.theme
    property real contentHeight: col.implicitHeight + 20
    onContentHeightChanged: bridge.setContentHeight(contentHeight)
    Component.onCompleted: bridge.setContentHeight(contentHeight)

    Column {
        id: col
        x: Math.round(4 * th.s); y: Math.round(6 * th.s)
        width: root.width - 2 * Math.round(4 * th.s)
        spacing: Math.round(8 * th.s)

        // ---- header ----------------------------------------------------------------------
        Rectangle {
            width: parent.width
            height: head.implicitHeight + 20
            radius: Math.round(6 * th.s)
            color: th.card
            Column {
                id: head
                x: Math.round(10 * th.s); y: Math.round(10 * th.s)
                width: parent.width - 20
                spacing: Math.round(8 * th.s)
                Row {
                    spacing: Math.round(10 * th.s)
                    Image { source: bridge.iconUrl; width: Math.round(34 * th.s); height: Math.round(34 * th.s); sourceSize.width: Math.round(68 * th.s); sourceSize.height: Math.round(68 * th.s) }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: bridge.title; color: th.text; font.pixelSize: Math.round(15 * th.s); font.family: th.family; font.bold: true }
                        Text { text: bridge.subtitle; color: th.muted; font.pixelSize: Math.round(11 * th.s); font.family: th.family }
                    }
                }
                Flow {
                    width: parent.width
                    spacing: Math.round(6 * th.s)
                    visible: bridge.info.length > 0
                    Repeater {
                        model: bridge.info
                        InfoChip { th: root.th; item: modelData; width: Math.floor((head.width - Math.round(6 * th.s)) / 2) - 1 }
                    }
                }
            }
        }

        // ---- search (property editor) -----------------------------------------------------
        Rectangle {
            visible: bridge.searchable
            width: parent.width
            height: visible ? Math.round(30 * th.s) : 0
            radius: Math.round(7 * th.s)
            color: th.field
            border.width: search.activeFocus ? 1 : 0
            border.color: th.accent
            Text { x: Math.round(9 * th.s); anchors.verticalCenter: parent.verticalCenter; text: "⌕"; color: th.muted; font.pixelSize: Math.round(14 * th.s) }
            TextInput {
                id: search
                anchors.fill: parent
                anchors.leftMargin: Math.round(28 * th.s); anchors.rightMargin: Math.round(8 * th.s)
                verticalAlignment: TextInput.AlignVCenter
                color: th.text
                selectionColor: th.accent
                font.pixelSize: Math.round(12 * th.s); font.family: th.family
                selectByMouse: true
                onTextChanged: bridge.setFilter(text)
                Text { anchors.verticalCenter: parent.verticalCenter; visible: !search.text.length; text: "Search properties"; color: th.muted; font.pixelSize: Math.round(12 * th.s); font.family: th.family }
            }
        }

        // ---- error banner ----------------------------------------------------------------
        Rectangle {
            width: parent.width
            height: errText.implicitHeight + 16
            radius: Math.round(8 * th.s)
            visible: bridge.error.length > 0
            color: Qt.rgba(0.88, 0.35, 0.32, 0.16)
            border.color: th.bad
            Text {
                id: errText
                x: Math.round(10 * th.s); y: Math.round(8 * th.s)
                width: parent.width - 20
                text: bridge.error
                color: th.bad
                wrapMode: Text.WordWrap
                font.pixelSize: Math.round(12 * th.s); font.family: th.family
            }
        }

        // ---- hint + actions --------------------------------------------------------------
        Rectangle {
            width: parent.width
            height: refCol.implicitHeight + 20
            radius: Math.round(6 * th.s)
            color: th.card
            visible: bridge.actions.length > 0
            Column {
                id: refCol
                x: Math.round(10 * th.s); y: Math.round(10 * th.s)
                width: parent.width - 20
                spacing: Math.round(8 * th.s)
                Text {
                    width: parent.width
                    visible: text.length > 0
                    text: bridge.hint
                    color: th.muted
                    font.pixelSize: Math.round(12 * th.s); font.family: th.family
                    wrapMode: Text.WordWrap
                }
                Flow {
                    width: parent.width
                    spacing: Math.round(6 * th.s)
                    Repeater {
                        model: bridge.actions
                        PillButton {
                            th: root.th
                            label: modelData.label
                            primary: modelData.primary === true
                            active: bridge.activeActions.indexOf(modelData.name) >= 0
                            onClicked: bridge.trigger(modelData.name)
                        }
                    }
                }
            }
        }

        // ---- parameter sections ----------------------------------------------------------
        Repeater {
            model: bridge.sections
            Section { th: root.th; section: modelData; width: col.width }
        }
    }
}

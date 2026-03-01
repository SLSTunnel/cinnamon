const Applet = imports.ui.applet;
const Gio = imports.gi.Gio;
const Lang = imports.lang;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;
const Tooltips = imports.ui.tooltips;
const Util = imports.misc.util;

const COLOR_SCHEMA = "org.lemon.settings-daemon.plugins.color";
const NIGHT_LIGHT_ENABLED_KEY = "night-light-enabled";
const NIGHT_LIGHT_TEMPERATURE_KEY = "night-light-temperature";

// Night light color temperature range in Kelvin (warmer = lower value)
const MIN_TEMPERATURE = 1000;
const MAX_TEMPERATURE = 6500;

class NightLightTemperatureSlider extends PopupMenu.PopupSliderMenuItem {
    constructor(gsettings) {
        let temp = gsettings.get_uint(NIGHT_LIGHT_TEMPERATURE_KEY);
        let clampedTemp = Math.max(MIN_TEMPERATURE, Math.min(MAX_TEMPERATURE, temp));
        // Slider 0 (left) = cooler (MAX_TEMPERATURE), slider 1 (right) = warmer (MIN_TEMPERATURE)
        let value = (MAX_TEMPERATURE - clampedTemp) / (MAX_TEMPERATURE - MIN_TEMPERATURE);
        super(value);

        this._gsettings = gsettings;
        this._seeking = false;

        this.tooltip = new Tooltips.Tooltip(this.actor, "%dK".format(clampedTemp));

        this.connect("drag-begin", () => { this._seeking = true; });
        this.connect("drag-end", () => { this._seeking = false; });
        this.connect("value-changed", Lang.bind(this, this._onValueChanged));
    }

    _onValueChanged() {
        let temp = Math.round(MAX_TEMPERATURE - this._value * (MAX_TEMPERATURE - MIN_TEMPERATURE));
        this._gsettings.set_uint(NIGHT_LIGHT_TEMPERATURE_KEY, temp);
        this.tooltip.set_text("%dK".format(temp));
    }

    syncFromSettings() {
        if (this._seeking)
            return;
        let temp = this._gsettings.get_uint(NIGHT_LIGHT_TEMPERATURE_KEY);
        let value = (MAX_TEMPERATURE - Math.max(MIN_TEMPERATURE, Math.min(MAX_TEMPERATURE, temp))) /
                    (MAX_TEMPERATURE - MIN_TEMPERATURE);
        this.setValue(value);
        this.tooltip.set_text("%dK".format(temp));
    }
}

class NightLightSwitch extends Applet.IconApplet {
    constructor(metadata, orientation, panelHeight, instance_id) {
        super(orientation, panelHeight, instance_id);

        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager.addMenu(this.menu);

        this.gsettings = Gio.Settings.new(COLOR_SCHEMA);
        this.nightLightEnabled = this.gsettings.get_boolean(NIGHT_LIGHT_ENABLED_KEY);
        this.connectColorID = this.gsettings.connect("changed", Lang.bind(this, this._onSettingsChanged));

        this._buildMenu();
        this._updateIcon();
        this._addContextMenuItems();
    }

    _buildMenu() {
        // On/off toggle switch
        this._enableSwitch = new PopupMenu.PopupSwitchMenuItem(_("Night Light"), this.nightLightEnabled);
        this._enableSwitch.connect('toggled', () => {
            this.gsettings.set_boolean(NIGHT_LIGHT_ENABLED_KEY, this._enableSwitch.state);
        });
        this.menu.addMenuItem(this._enableSwitch);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Color temperature section header
        let colorTempHeader = new PopupMenu.PopupMenuItem(_("Color Temperature"), { reactive: false });
        this.menu.addMenuItem(colorTempHeader);

        // Temperature slider: warmer (right/1) ↔ cooler (left/0)
        this._tempSlider = new NightLightTemperatureSlider(this.gsettings);
        this.menu.addMenuItem(this._tempSlider);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Settings link
        this.menu.addSettingsAction(_("Night Light Settings"), 'nightlight');
    }

    _addContextMenuItems() {
        let items = this._applet_context_menu._getMenuItems();
        if (this.context_menu_item_configure == null) {
            this.context_menu_item_configure = new PopupMenu.PopupIconMenuItem(_("Configure..."),
                "xsi-preferences",
                St.IconType.SYMBOLIC);
            this.context_menu_item_configure.connect('activate',
                () => { Util.spawnCommandLineAsync("lemon-settings nightlight"); }
            );
        }
        if (items.indexOf(this.context_menu_item_configure) == -1) {
            this._applet_context_menu.addMenuItem(this.context_menu_item_configure);
        }
    }

    _onSettingsChanged() {
        let enabled = this.gsettings.get_boolean(NIGHT_LIGHT_ENABLED_KEY);
        if (enabled !== this.nightLightEnabled) {
            this.nightLightEnabled = enabled;
            this._enableSwitch.setToggleState(enabled);
            this._updateIcon();
        }
        this._tempSlider.syncFromSettings();
    }

    _updateIcon() {
        if (this.nightLightEnabled) {
            this.set_applet_icon_symbolic_name("xsi-night-light-symbolic");
            this.set_applet_tooltip(_("Night Light: On"));
        } else {
            this.set_applet_icon_symbolic_name("xsi-night-light-disabled-symbolic");
            this.set_applet_tooltip(_("Night Light: Off"));
        }
    }

    on_applet_clicked() {
        this.menu.toggle();
    }

    on_applet_removed_from_panel() {
        this.gsettings.disconnect(this.connectColorID);
    }
}

function main(metadata, orientation, panel_height, instance_id) {
    return new NightLightSwitch(metadata, orientation, panel_height, instance_id);
}

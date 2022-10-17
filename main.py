#!/usr/bin/python3
import sys
import signal
from gi.repository import GLib
import bluetooth_utils
import bluetooth_constants
import dbus
import dbus.mainloop.glib
from mqtt_manager import *
import json

sys.path.insert(0, ".")

adapter_interface = None
mainloop = None
timer_id = None

devices = {}
managed_objects_found = 0

scantime = 20000

bus = None
device_interface = None

addedSignalReceiver = None

device_interface = None
device_path = None
found_ws = False
found_tc = False
ws_path = None
tc_path = None

mqtt = None


def temperature_received(interface, changed, invalidated, path):
    if "Value" in changed:
        temperature = bluetooth_utils.dbus_to_python(changed["Value"])
        message = "temperature: " + str(temperature[0]) + "C"

        print(message)
        mqtt_pub("thingy52", message, 0)


def start_notifications():
    global tc_path
    global bus
    char_proxy = bus.get_object("org.bluez", tc_path)
    char_interface = dbus.Interface(char_proxy, "org.bluez.GattCharacteristic1")
    bus.add_signal_receiver(
        temperature_received,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path=tc_path,
        path_keyword="path",
    )

    try:
        print("Starting notifications")
        char_interface.StartNotify()
        print("Done starting notifications")
    except Exception as e:
        print("Failed to start temperature notifications")
        print(e.get_dbus_name())
        print(e.get_dbus_message())
        return bluetooth_constants.RESULT_EXCEPTION
    else:
        return bluetooth_constants.RESULT_OK


def mqtt_pub(topic, msg, qos):
    global mqtt
    mqtt.publish(topic, msg, qos)


def mqtt_connect():
    global mqtt
    mqtt.connect()


def service_discovery_completed():
    global found_ws
    global found_tc
    global ws_path
    global tc_path
    global bus

    if found_ws and found_tc:
        print("Required service and characteristic found - device is OK")
        print("Weather service path: ", ws_path)
        print("Temperature characteristic path: ", tc_path)

        addedSignalReceiver.remove()
        print("MQTT connecting....")
        mqtt_connect()
        start_notifications()
    else:
        print("Required service and characteristic were not found - device is NOK")
        print("Weather service found: ", str(found_ws))
        print("Temperature characteristic found: ", str(found_tc))
        bus.remove_signal_receiver(interfaces_added, "InterfacesAdded")
        bus.remove_signal_receiver(properties_changed, "PropertiesChanged")
    print("-------------------------------------------------------------------")
    # mainloop.quit()


def properties_changed(interface, changed, invalidated, path):
    global device_path

    if path == device_path:
        if "ServicesResolved" in changed:
            sr = bluetooth_utils.dbus_to_python(changed["ServicesResolved"])
            print("ServicesResolved : ", sr)
            if sr == True:
                service_discovery_completed()


def interfaces_removed(path, interfaces):
    # interfaces is an array of dictionary entries
    if not "org.bluez.Device1" in interfaces:
        return
    if path in devices:
        dev = devices[path]
        if "Address" in dev:
            print("DEL bdaddr: ", bluetooth_utils.dbus_to_python(dev["Address"]))
        else:
            print("DEL path : ", path)

        print("-------------------------------------------------------------------")
        del devices[path]


def interfaces_added(path, interfaces):
    global found_ws
    global found_tc
    global ws_path
    global tc_path

    if "org.bluez.Device1" in interfaces:
        device_properties = interfaces["org.bluez.Device1"]
        if path not in devices:
            print("NEW path :", path)
            devices[path] = device_properties
            dev = devices[path]

            if "Address" in dev:
                print("NEW bdaddr: ", bluetooth_utils.dbus_to_python(dev["Address"]))
            if "Name" in dev:
                print("NEW name : ", bluetooth_utils.dbus_to_python(dev["Name"]))
            if "RSSI" in dev:
                print("NEW RSSI : ", bluetooth_utils.dbus_to_python(dev["RSSI"]))
            print("-------------------------------------------------------------------")
        return

    if "org.bluez.GattService1" in interfaces:
        properties = interfaces["org.bluez.GattService1"]
        print("-------------------------------------------------------------------")
        print("SVC path   :", path)
        if "UUID" in properties:
            uuid = properties["UUID"]
            if uuid == bluetooth_constants.WEATHER_SVC_UUID:
                found_ws = True
                ws_path = path
            print("SVC UUID   : ", bluetooth_utils.dbus_to_python(uuid))
            print("SVC name   : ", bluetooth_utils.get_name_from_uuid(uuid))
        return

    if "org.bluez.GattCharacteristic1" in interfaces:
        properties = interfaces["org.bluez.GattCharacteristic1"]
        print("   CHR path   :", path)
        if "UUID" in properties:
            uuid = properties["UUID"]
            if uuid == bluetooth_constants.TEMPERATURE_CHR_UUID:
                found_tc = True
                tc_path = path
            print("   CHR UUID   : ", bluetooth_utils.dbus_to_python(uuid))
            print("   CHR name   : ", bluetooth_utils.get_name_from_uuid(uuid))
            flags = ""
            for flag in properties["Flags"]:
                flags += flag + ","
            print("   CHR flags   : ", flags)
        return

    if "org.bluez.GattDescriptor1" in interfaces:
        properties = interfaces["org.bluez.GattDescriptor1"]
        print("      DSC path   :", path)
        if "UUID" in properties:
            uuid = properties["UUID"]
            print("      DSC UUID   : ", bluetooth_utils.dbus_to_python(uuid))
            print("      DSC name   : ", bluetooth_utils.get_name_from_uuid(uuid))
        return


def device_info(device_proxy):
    device_properties = dbus.Interface(device_proxy, "org.freedesktop.DBus.Properties")
    print("Connected Bluetooth device general information:")
    print("Device name: %s" % device_properties.Get("org.bluez.Device1", "Name"))
    print("Device address: %s" % device_properties.Get("org.bluez.Device1", "Address"))
    status = (
        "Successful connection"
        if device_properties.Get("org.bluez.Device1", "Connected") == 1
        else "Failed connection"
    )
    print(f"Device status: {status}")


def connect():
    global bus
    global device_interface
    try:
        device_interface.Connect()
    except Exception as e:
        print("Failed to connect")
        print(e.get_dbus_name())
        print(e.get_dbus_message())
        if "UnknownObject" in e.get_dbus_name():
            print("Try scanning first to resolve this problem")
        return 7
    else:
        print("Connected OK")
    print("*******************************************************************")
    return 1


def list_devices_found():
    global devices
    print("Full list of devices", len(devices), "discovered:")
    for path in devices:
        dev = devices[path]
        if "Name" in dev:
            print(bluetooth_utils.dbus_to_python(dev["Address"]), end="")
            print(" Device's name : ", bluetooth_utils.dbus_to_python(dev["Name"]))
        else:
            print(bluetooth_utils.dbus_to_python(dev["Address"]))
    print("-------------------------------------------------------------------")


def discover_timeout():
    global timer_id
    global mainloop
    global adapter_interface
    global addedSignalReceiver

    print("discovery done!!!!!!!!!!!")

    GLib.source_remove(timer_id)
    mainloop.quit()
    adapter_interface.StopDiscovery()

    bus = dbus.SystemBus()
    # bus.remove_signal_receiver(interfaces_added,"InterfacesAdded")
    addedSignalReceiver.remove()
    list_devices_found()
    return True


def discover_devices(bus: dbus.SystemBus):
    global adapter_interface
    global mainloop
    global timer_id
    global scantime
    global addedSignalReceiver

    adapter_path = "/org/bluez/hci0"
    adapter_proxy = bus.get_object("org.bluez", adapter_path)
    adapter_interface = dbus.Interface(adapter_proxy, "org.bluez.Adapter1")
    addedSignalReceiver = bus.add_signal_receiver(
        interfaces_added,
        dbus_interface="org.freedesktop.DBus.ObjectManager",
        signal_name="InterfacesAdded",
    )

    timer_id = GLib.timeout_add(scantime, discover_timeout)
    adapter_interface.StartDiscovery(byte_arrays=True)


def get_know_devices(bus):
    global managed_objects_found
    object_manager = dbus.Interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )
    managed_objects = object_manager.GetManagedObjects()

    for path, ifaces in managed_objects.items():
        for iface_name in ifaces:
            if iface_name == "org.bluez.Device1":
                managed_objects_found += 1
                print("EXI path : ", path)
                device_properties = ifaces["org.bluez.Device1"]
                devices[path] = device_properties
                if "Address" in device_properties:
                    print(
                        "EXI bdaddr: ",
                        bluetooth_utils.dbus_to_python(device_properties["Address"]),
                    )
                    print(
                        "-------------------------------------------------------------------"
                    )


def disconnect():
    global bus
    global device_interface
    try:
        device_interface.Disconnect()
    except Exception as e:
        print("Failed to disconnect")
        print(e.get_dbus_name())
        print(e.get_dbus_message())
        return 7
    else:
        print("Disconnected OK")
        return 1


if __name__ == "__main__":
    mqtt = MqttManager()

    # dbus initialisation steps
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    print("Listing devices already known to BlueZ:")
    get_know_devices(bus)
    print("Found ", managed_objects_found, " managed device objects")
    print("-------------------------------------------------------------------")

    print("Scanning Devices....")
    mainloop = GLib.MainLoop()
    discover_devices(bus)
    mainloop.run()
    print("*******************************************************************")

    connect_addr = input(
        "Input a Bluetooth device address from above list want to connect: "
    )
    print(f"Connecting to {connect_addr}....")

    adapter_path = "/org/bluez/" + "hci0"
    device_path = bluetooth_utils.device_address_to_path(connect_addr, adapter_path)
    device_proxy = bus.get_object("org.bluez", device_path)
    device_interface = dbus.Interface(device_proxy, "org.bluez.Device1")
    connect()
    device_info(device_proxy)
    print("*******************************************************************")

    print("Discovering services....")
    addedSignalReceiver = bus.add_signal_receiver(
        interfaces_added,
        dbus_interface="org.freedesktop.DBus.ObjectManager",
        signal_name="InterfacesAdded",
    )
    bus.add_signal_receiver(
        properties_changed,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path_keyword="path",
    )
    mainloop.run()

    # while True:
    #     remove_device = input('Do you wanna disconnect? y/n ')
    #     if remove_device == 'y':
    #         disconnect()
    #         break
    #     elif remove_device =='n':
    #         pass
    #     else:
    #         print('Wrong input, try again.')

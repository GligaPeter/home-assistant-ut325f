DOMAIN = "ut325f_ble"
SERVICE_UUID = "0000ff12-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
FRAME_HEADER = b"\xaa\x55\x00\x34\x01"
FRAME_SIZE = 53

THERMOCOUPLE_TYPES = {
    0: "K",
    1: "J",
    2: "T",
    3: "E",
    4: "R",
    5: "S",
    6: "N",
    7: "B",
}

CHANNEL_STATES = {
    0: "ok",
    1: "under_range",
    2: "over_range",
    3: "disconnected",
}

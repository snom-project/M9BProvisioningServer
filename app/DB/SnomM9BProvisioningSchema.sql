-- Schema for SnomM9B Bluetooth Gateways
create table SnomM9BDevices (
    ipei        text,
    type        text default "rtx8200",
    revision    integer default 1,
    data        string default "",
    UNIQUE(ipei, revision)
);



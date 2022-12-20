import pytest
import time
import datetime
import json
from tests.common.utilities import wait_until

pytestmark = [
    pytest.mark.topology('any'),
    pytest.mark.device_type('vs')
]


def test_isis_overload_on_start(duthosts, enum_frontend_dut_hostname):
    """test basic functionality of set overload on start"""

    duthost = duthosts[enum_frontend_dut_hostname]
    overload_on_startup_time = 120

    # Verfiy isisd is running
    assert check_isisd_running(duthost)

    # Configure simple config with set overload on startup
    frr_config = """
    configure
    router isis 1
      is-type level-2-only
      net 49.0001.1720.1700.0002.00
      set-overload-bit on-startup {}
    exit
    interface PortChannel101
      ip router isis 1
      isis circuit-type level-2-only
      isis network point-to-point
      no isis hello padding
    end
    write memory
    """.format(overload_on_startup_time)

    vtysh_cmd = "vtysh -c \"{}\"".format(frr_config)
    duthost.shell(vtysh_cmd)

    # Restart sonic device
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    # Verfiy isisd is running
    assert wait_until(10, 1, 0, check_isisd_running, duthost)
    tstamp_on_startup = datetime.datetime.now()

    # Check that overload bit is set in the LSP
    assert check_lsp_overload_bit(duthost, "vlab-01.00-00", "0/0/1")

    # Check that overload bit is unset in the LSP
    assert wait_until(120, 1, 0, check_lsp_overload_bit, duthost, "vlab-01.00-00", "0/0/0")
    tstamp_on_overload_bit_unset = datetime.datetime.now()

    overload_time = (
        tstamp_on_overload_bit_unset - tstamp_on_startup
    ).total_seconds()
    assert overload_time >= overload_on_startup_time - 1  and overload_time <= overload_on_startup_time + 1

def test_cancel_overload_timer(duthosts, enum_frontend_dut_hostname):
    """test overload cancellation"""

    duthost = duthosts[enum_frontend_dut_hostname]
    overload_on_startup_time = 120

    # Configure set-overload-bit on-startup with set-overload-bit
    frr_config = """
    configure
    router isis 1
      set-overload-bit
      set-overload-bit on-startup {}
    end
    write memory
    """.format(overload_on_startup_time)

    vtysh_cmd = "vtysh -c \"{}\"".format(frr_config)
    duthost.shell(vtysh_cmd)

    # Restart sonic device
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    if not wait_until(10, 1, 0, check_isisd_running, duthost):
        sonic_db_cmd = "docker start bgp"
        duthost.shell(sonic_db_cmd)

    # Verfiy isisd is running
    assert wait_until(10, 1, 0, check_isisd_running, duthost)

    # Check that overload bit is set in the LSP
    assert check_lsp_overload_bit(duthost, "vlab-01.00-00", "0/0/1")

    # Unset overload bit while timer is running 
    frr_config = """
    configure
    router isis 1
      no set-overload-bit
    end
    write memory
    """

    vtysh_cmd = "vtysh -c \"{}\"".format(frr_config)
    duthost.shell(vtysh_cmd)
    
    assert check_isisd_running(duthost)
    # Check that overload bit is unset
    tstamp_before_unset = datetime.datetime.now()
    assert wait_until(10, 1, 0, check_lsp_overload_bit, duthost, "vlab-01.00-00", "0/0/0")
    tstamp_after_unset = datetime.datetime.now()

    overload_time = (
        tstamp_after_unset - tstamp_before_unset
    ).total_seconds()

    logging.info(overload_time)

def test_override_overload_timer(duthosts, enum_frontend_dut_hostname, enum_asic_index):
    """test override overload"""

    duthost = duthosts[enum_frontend_dut_hostname]
    overload_on_startup_time = 60

    # Configure set-overload-bit on-startup with set-overload-bit
    frr_config = """
    configure
    router isis 1
      set-overload-bit
      set-overload-bit on-startup {}
    end
    write memory
    """.format(overload_on_startup_time)

    vtysh_cmd = "vtysh -c \"{}\"".format(frr_config)
    duthost.shell(vtysh_cmd)

    # Restart sonic device
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    # Verfiy isisd is running
    assert wait_until(10, 1, 0, check_isisd_running, duthost)

    # Check that overload bit is set in the LSP
    assert check_lsp_overload_bit(duthost, "vlab-01.00-00", "0/0/1")

    # Wait for configured overload time - enough for overload timer to run out 
    time.sleep(overload_on_startup_time + 1)

    # Check that overload bit is still set in the LSP 
    assert check_lsp_overload_bit(duthost, "vlab-01.00-00", "0/0/1")

def check_isisd_running(duthost):
    sonic_db_cmd = "vtysh -c \"show daemons\""
    daemons = duthost.shell(sonic_db_cmd)['stdout_lines'][0]
    return "isisd" in daemons

def check_lsp_overload_bit(duthost, lsp, att_p_ol_expected):
    vtysh_cmd = "show isis database {} json".format(lsp)
    sonic_db_cmd = "vtysh -c \"{}\"".format(vtysh_cmd)
    output = duthost.shell(sonic_db_cmd)['stdout']
    database_json = json.loads(output)
    att_p_ol = database_json["areas"][0]["levels"][1]["att-p-ol"]
    return att_p_ol == att_p_ol_expected

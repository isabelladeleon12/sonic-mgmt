import pytest
import time
from utilities.common import poll_wait

pytestmark = [
    pytest.mark.topology('any'),
    pytest.mark.device_type('vs')
]


def test_isis_overload_on_start(duthosts, enum_frontend_dut_hostname, enum_asic_index):
    """test basic functionality of set overload on start"""

    duthost = duthosts[enum_frontend_dut_hostname]

    bgp_facts = duthost.bgp_facts(instance_id=enum_asic_index)['ansible_facts']
    namespace = duthost.get_namespace_from_asic_id(enum_asic_index)
    config_facts = duthost.config_facts(host=duthost.hostname, source="running", namespace=namespace)['ansible_facts']

    # Verfiy isisd is running
    assert check_isisd_running()

    # Configure set-overload-bit on-startup
    sonic_db_cmd = "vtysh -c \"configure\nrouter isis 1\nset-overload-bit on-startup 120\nend\""
    duthost.shell(sonic_db_cmd)

    # Restart sonic device
    tstamp_before_restart_router = datetime.datetime.now()
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    assert poll_wait(check_isisd_running, 60)

    tstamp_after_restart_router = datetime.datetime.now()
    startup_router_time = (
        tstamp_after_start_router - tstamp_before_start_router
    ).total_seconds()

    # Check that overload bit is set in the LSP
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/1")
    time.sleep(120)

    # Check that overload bit is unset in the LSP
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/0")

def test_cancel_overload_timer(duthosts, enum_frontend_dut_hostname, enum_asic_index):
    """test overload cancellation"""

    # Configure set-overload-bit on-startup with set-overload-bit
    sonic_db_cmd = "vtysh -c \"configure\nrouter isis 1\nset-overload-bit on-startup 120\nset-overload-bit\nend\""
    duthost.shell(sonic_db_cmd)

    # Restart sonic device
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    # Wait for isisd to start up
    assert poll_wait(check_isisd_running, 60)

    # Check that overload bit is set in the LSP 
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/1")

    # Unset overload bit while timer is running 
    sonic_db_cmd = "vtysh -c \"configure\nrouter isis 1\nno set-overload-bit\nend\""
    duthost.shell(sonic_db_cmd)

    # Check that overload bit is unset
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/0")

def test_override_overload_timer(duthosts, enum_frontend_dut_hostname, enum_asic_index):
    """test override overload"""
    # Configure set-overload-bit on-startup with set-overload-bit
    sonic_db_cmd = "vtysh -c \"configure\nrouter isis 1\nset-overload-bit on-startup 60\nset-overload-bit\nend\""
    duthost.shell(sonic_db_cmd)

    # Restart sonic device
    sonic_db_cmd = "sudo systemctl restart bgp"
    duthost.shell(sonic_db_cmd)

    # Wait for isisd to start up
    assert poll_wait(check_isisd_running, 60)

    # Check that overload bit is set in the LSP 
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/1")

    # Wait for 60 seconds - enough for overload timer to run out 
    time.sleep(60)

    # Check that overload bit is still set in the LSP 
    assert check_lsp_overload_bit("vlab-01.00-00", "0/0/1")

def check_isisd_running():
    sonic_db_cmd = "vtysh -c \"show daemons\""
    daemons = duthost.shell(sonic_db_cmd)['stdout_lines'][0]
    return "isisd" in daemons

def check_lsp_overload_bit(lsp, att_p_ol_expected):
    vtysh_cmd = "show isis database {} json".format(sp)
    sonic_db_cmd = f"vtysh -c \"{vtysh_cmd}\""
    output = duthost.shell(sonic_db_cmd)['stdout_lines'][0]
    database_json = json.loads(output)
    att_p_ol = database_json["areas"][0]["levels"][1]["att-p-ol"]
    return att_p_ol == att_p_ol_expected:






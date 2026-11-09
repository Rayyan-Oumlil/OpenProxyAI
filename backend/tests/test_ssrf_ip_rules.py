"""The one rule for 'may the gateway connect to this address': shared by save-time validation and the connection guard."""

import pytest

from app.utils.ssrf import ip_allowed, never_allowed_ip

PUBLIC = ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "93.184.216.34"]
PRIVATE = ["10.0.0.5", "172.16.0.1", "192.168.1.10", "127.0.0.1", "::1", "100.64.0.1", "fc00::1"]  # RFC1918, loopback, CGN, ULA
NEVER = [
	"169.254.169.254", "169.254.0.1", "fe80::1", "fd00:ec2::254", "0.0.0.0", "::", "224.0.0.1", "ff02::1",
	"::ffff:169.254.169.254",  # metadata address in IPv6 clothing
	"::ffff:0.0.0.0", "fe80::1%eth0",
]


@pytest.mark.parametrize("ip", PUBLIC)
def test_public_addresses_are_allowed_everywhere(ip):
	assert ip_allowed(ip, internal=False) and ip_allowed(ip, internal=True)


@pytest.mark.parametrize("ip", PRIVATE)
def test_private_addresses_need_an_internal_endpoint(ip):
	assert not ip_allowed(ip, internal=False)
	assert ip_allowed(ip, internal=True)


@pytest.mark.parametrize("ip", NEVER)
def test_metadata_link_local_multicast_and_unspecified_are_never_allowed(ip):
	assert never_allowed_ip(ip)
	assert not ip_allowed(ip, internal=False) and not ip_allowed(ip, internal=True)


@pytest.mark.parametrize("junk", ["", "not-an-ip", "999.1.1.1", "1.2.3"])
def test_anything_that_is_not_an_address_is_refused(junk):
	assert not ip_allowed(junk, internal=True) and not ip_allowed(junk, internal=False)


def test_ipv4_mapped_private_addresses_are_judged_as_the_ipv4_address():
	assert not ip_allowed("::ffff:10.0.0.5", internal=False)
	assert ip_allowed("::ffff:10.0.0.5", internal=True)
	assert ip_allowed("::ffff:8.8.8.8", internal=False)

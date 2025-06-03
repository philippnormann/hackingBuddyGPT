from hackingBuddyGPT.utils.shell_root_detection import got_root


def test_got_root():
    hostname = "i_dont_care"

    # Basic root/user prompts
    assert got_root(hostname, "# ") is True
    assert got_root(hostname, "$ ") is False
    assert got_root(hostname, "#") is True   # No space
    assert got_root(hostname, "$") is False  # No space

    # Bash version prompts
    assert got_root(hostname, "bash-5.2#") is True
    assert got_root(hostname, "bash-5.2$") is False
    assert got_root(hostname, "bash-3.2.57#") is True    # Different version
    assert got_root(hostname, "bash-4.4.20#") is True    # Different version
    assert got_root(hostname, "bash-5.2# ") is True      # With space
    
    # Full prompts with hostname and path
    assert got_root(hostname, "root@56421866fc31:/home/lowpriv#") is True
    assert got_root(hostname, "lowpriv@28eb218c3969:/root/") is False
    assert got_root(hostname, "root@localhost:~#") is True             # Simple hostname
    assert got_root(hostname, "root@server-01.example.com:/var/log#") is True  # Complex hostname
    assert got_root(hostname, "root@kali:~# ") is True                # With space

    # Sometimes we get doulbe prompts, so we should handle that
    assert got_root(hostname, " / # / #  ") is True  # Double prompt with spaces
    assert got_root(hostname, "root@kali:~# root@kali:~# ") is True  # Double prompt
    assert got_root(hostname, "root@kali:~# lowpriv@kali:~$ ") is False  # Double prompt with lowpriv
    assert got_root(hostname, "lowpriv@kali:~$ root@kali:~# ") is True  # Double prompt with root at the end
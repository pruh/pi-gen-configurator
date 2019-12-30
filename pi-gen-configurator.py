#!/usr/bin/env python3

import os
import sys
import logging
import fileinput
import shutil
import getpass
import subprocess
import argparse

from io import BytesIO
from zipfile import ZipFile
import requests

from git import Repo


class ConfiguratorError(Exception):
    pass


class MaxLevelFilter(object):

    def __init__(self, max_level):
        self.max_level = max_level

    def filter(self, record):
        return record.levelno <= self.max_level


formatter = logging.Formatter('%(asctime)s [%(threadName)18s][%(module)14s][%(levelname)8s] %(message)s')

# Redirect messages lower or equal than INFO to stdout
stdout_hdlr = logging.StreamHandler(sys.stdout)
stdout_hdlr.setFormatter(formatter)
log_filter = MaxLevelFilter(logging.INFO)
stdout_hdlr.addFilter(log_filter)
stdout_hdlr.setLevel(logging.DEBUG)

# Redirect messages higher or equal than WARNING to stderr
stderr_hdlr = logging.StreamHandler(sys.stderr)
stderr_hdlr.setFormatter(formatter)
stderr_hdlr.setLevel(logging.WARNING)

file_hdlr = logging.FileHandler('build.log')
file_hdlr.setFormatter(formatter)

log = logging.getLogger()
log.addHandler(stdout_hdlr)
log.addHandler(stderr_hdlr)
log.addHandler(file_hdlr) 

log.setLevel(logging.DEBUG)


def main():
    sys.excepthook = handle_exception

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--hostname', action='store', type=str, help='hostname')
    parser.add_argument('-u', '--username', action='store', type=str, help='username')
    parser.add_argument('-p', '--password', action='store', type=str, help='user password')
    parser.add_argument('-c', '--country-code', action='store', type=str, help='WiFi Country Code (can be found at https://en.wikipedia.org/wiki/ISO_3166-1)')
    parser.add_argument('-s', '--ssid', action='store', type=str, help='WiFi SSID')
    parser.add_argument('-w', '--passphrase', action='store', type=str, help='WiFi Passphrase')
    parser.add_argument('--skip-ngrok', action='store_true', help='skip ngrok')
    parser.add_argument('-a', '--authtoken', action='store', type=str, help='ngrok auth token')
    parser.add_argument('-l', '--locale', action='store', type=str, help='locale (e.g. en_US.UTF-8)')
    parser.add_argument('-t', '--timezone', action='store', type=str, help='timezone (e.g. America/New_York, '
            'can be found at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)')
    parser.add_argument('-k', '--keymap', action='store', type=str, help='keyboard keymap (gb, us, etc.)')
    parser.add_argument('-y', '--layout', action='store', type=str, help='keyboard layout (English (US), English (UK), etc.)')
    args = parser.parse_args()

    _remove_leftovers()

    _clone_pi_gen()

    _change_user_and_password(username=args.username, password=args.password)

    _set_wifi_settings(country_code=args.country_code, ssid=args.ssid, passphrase=args.passphrase)

    _enable_ssh()

    _install_ngrok(skip_ngrok=args.skip_ngrok, authtoken=args.authtoken)

    _change_locale(locale=args.locale)

    _change_timezone(timezone=args.timezone)

    _change_keyborad_layout(keymap=args.keymap, layout=args.layout)

    _build_image(hostname=args.hostname)

    _copy_artifacts()

    _clean_up()


# Exception handler will log unhandled exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    log.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


def _remove_leftovers():
    if os.path.exists('./artifacts'):
        shutil.rmtree('./artifacts')

    # TODO not removing if running
    container_name = 'pigen_work'
    with subprocess.Popen(f'[ $(docker ps -a -q -f name={container_name}) ] && docker rm -v {container_name} || true',
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
            universal_newlines=True) as proc:
        exit_code = proc.wait()
        if exit_code != 0:
            stderr = ", ".join(map(lambda s: s.rstrip(), proc.stderr.readlines()))
            log.error(f"failed to remove previous docker container with error code {exit_code} " \
                f"and stderr: {stderr}")
            raise ConfiguratorError(f'Cannot build image')


def _clone_pi_gen():
    # Clone specific commit to avoid possible issues
    repo_str = 'git@github.com:RPi-Distro/pi-gen.git'
    sha1 = '5436273ec728c8369dab9c08f2739805f20510f7'

    repo_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pi-gen', '')

    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)

    log.info(f'cloning {repo_str} to {repo_dir}')
    repo = Repo.clone_from(repo_str, repo_dir)

    log.info(f'checking out {sha1}')
    repo.head.reset(commit=sha1)


def _change_user_and_password(username=None, password=None):
    if not username:
        username = input("What is your username: ")
    if not password:
        password = getpass.getpass("What is your password: ")

    files_dir = 'pi-gen/stage2/03-username-password/'
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)

    run_file = os.path.join(files_dir, '00-run.sh')
    with open(run_file, "w") as f:
        f.write('#!/bin/bash -e'
                '\n'
                'on_chroot << EOF\n'
                f'usermod -l {username} pi\n'
                f'usermod -m -d /home/{username} {username}\n'
                f'echo -e "{password}\n{password}" | passwd {username}\n'
                'EOF\n')

    os.chmod(run_file, 0o755)


def _set_wifi_settings(country_code=None, ssid=None, passphrase=None):
    if not country_code:
        country_code = input("What is your country alpha-2 code (can be found at https://en.wikipedia.org/wiki/ISO_3166-1): ")
        while not country_code or len(country_code) is not 2:
            country_code = input("Please re-type your country code: ")
    
    if not ssid:
        ssid = input("What is your wifi SSID: ")
    if not passphrase:
        passphrase = getpass.getpass("Please enter WiFi's passphrase: ")

    filename = 'pi-gen/stage2/02-net-tweaks/files/wpa_supplicant.conf'
    with fileinput.input(filename, inplace=True) as f:
        for line in f:
            if fileinput.isfirstline():
                print(f'country={country_code}')

            print(line, end='')

    run_file = 'pi-gen/stage2/02-net-tweaks/02-run.sh'
    with open(run_file, "w") as f:
        f.write('#!/bin/bash -e'
                '\n'
                'echo "adding wifi network to /etc/wpa_supplicant/wpa_supplicant.conf"\n'
                'on_chroot << EOF\n'
                '  echo "" >> /etc/wpa_supplicant/wpa_supplicant.conf\n'
                f'  wpa_passphrase \"{ssid}\" \"{passphrase}\" | sed \'/^[ \\t]*#/ d\' >> /etc/wpa_supplicant/wpa_supplicant.conf\n'
                'EOF\n')

    os.chmod(run_file, 0o755)


def _enable_ssh():
    dirname = 'pi-gen/export-image/03-finalise/'
    filename = '00-run.sh'
    full_path = os.path.join(dirname, filename)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(full_path, "w") as f:
        f.write('#!/bin/bash -e\n\n# Enable SSH daemon by default.\ntouch "$ROOTFS_DIR"/boot/ssh')

    os.chmod(full_path, 0o755)


def _install_ngrok(skip_ngrok=False, authtoken=None):
    if skip_ngrok:
        return

    if authtoken:
        yes_no = 'yes'
    else:
        yes_no = query_yes_no('do you want to set up ngrok', 'no')
    if not yes_no:
        return

    target_dir = 'pi-gen/stage2/04-custom-installations/'
    files_dirname = 'files'
    files_dir = os.path.join(target_dir, files_dirname, '')

    if not os.path.exists(files_dir):
        os.makedirs(files_dir)

    _download_ngrok(files_dir)

    config_file = 'ssh_config.yml'
    _create_ngrok_config(files_dir, config_file, authtoken)

    start_script_file = 'start_tunnel'
    _add_ngrok_cronjob(files_dir, start_script_file)

    run_file = os.path.join(target_dir, '00-run.sh')
    with open(run_file, "w") as f:
        f.write('#!/bin/bash -e\n\n'
                '# Copy ngrok to /usr/local/bin.\n'
                'install -d "${ROOTFS_DIR}/usr/local/bin"\n'
                f'install -m 755 {files_dirname}/ngrok "${{ROOTFS_DIR}}/usr/local/bin/"\n\n'
                '# Copy ngrok config to /etc/opt/scripts/ngrok\n'
                'install -d "${ROOTFS_DIR}/etc/opt/scripts/ngrok"\n'
                f'install -m 644 {files_dirname}/{config_file} "${{ROOTFS_DIR}}/etc/opt/scripts/ngrok/"\n\n'
                '# Copy ngrok start script to /etc/cron.hourly/\n'
                'install -d "${ROOTFS_DIR}/etc/cron.hourly/"\n'
                f'install -m 755 {files_dirname}/{start_script_file} "${{ROOTFS_DIR}}/etc/cron.hourly/"\n')

    os.chmod(run_file, 0o755)


def _download_ngrok(files_dir):
    r = requests.get('https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-arm.zip')
    z = ZipFile(BytesIO(r.content))
    z.extractall(files_dir)

    for filename in os.listdir(files_dir):
        if not filename == 'ngrok':
            raise ConfiguratorError(f'should be ngrok file in archive, but was {filename}')


def _create_ngrok_config(files_dir, config_filename, authtoken=None):
    if not authtoken:
        authtoken = input("What is your ngrok authtoken: ")

    with open(os.path.join(files_dir, config_filename), "w") as f:
        f.write(f'authtoken: {authtoken}\n'
                'tunnels:\n'
                '  ssh:\n'
                '    proto: tcp\n'
                '    addr: 22\n')


def _add_ngrok_cronjob(files_dir, filename):
    with open(os.path.join(files_dir, filename), "w") as f:
        f.write('#!/bin/bash -e\n'
                '\n'
                '# This script checks if ngrok is not running and starts a tunnel if not.\n'
                '\n'
                'if ps -ax | grep ngrok | grep -q ssh ; then\n'
                '  echo "$HOSTNAME SSH tunnel is already created"\n'
                'else\n'
                '  echo "$HOSTNAME SSH tunnel is down, setting it up now" >&2\n'
                '  /usr/local/bin/ngrok start -config "/etc/opt/scripts/ngrok/ssh_config.yml" ssh > /dev/null &\n'
                '\n'
                '  status=$?\n'
                '  if [ $status -eq 0 ]; then\n'
                '    echo "tunnel should be started"\n'
                '  else\n'
                '    echo "cannot start tunnel" >&2\n'
                '  fi\n'
                'fi\n')


def _change_locale(locale):
    if not locale:
        locale = input("What locale to use (e.g. en_US.UTF-8): ")

    with fileinput.input('pi-gen/stage0/01-locale/00-debconf', inplace=True) as file:
        for line in file:
            print(line.replace("select\ten_GB.UTF-8", f"select\t{locale}"), end='')


def _change_timezone(timezone=None):
    if not timezone:
        timezone = input("What is your timezone (e.g. America/New_York)"
            "(can be found at https://en.wikipedia.org/wiki/List_of_tz_database_time_zones): ")

    run_dir = 'pi-gen/stage2/05-timezone'

    if not os.path.exists(run_dir):
        os.makedirs(run_dir)

    run_file = os.path.join(run_dir, '00-run.sh')
    with open(run_file, "w") as f:
        f.write('#!/bin/bash -e'
                '\n'
                f'echo "changing timezone to: {timezone}"\n'
                'on_chroot << EOF\n'
                '  unlink /etc/localtime\n'
                f'  echo \'{timezone}\' > /etc/timezone\n'
                '  dpkg-reconfigure tzdata\n'
                'EOF\n')

    os.chmod(run_file, 0o755)


def _change_keyborad_layout(keymap=None, layout=None):
    # TODO dynamically fetch all of the below
    # TODO should be from /usr/share/X11/xkb/symbols
    if not keymap:
        keymap = input("What is your keymap (gb, us, etc.): ")
    if not layout:
        layout = input("What is your keyboard layout (English (US), English (UK), etc.): ")

    with fileinput.input('pi-gen/stage2/01-sys-tweaks/00-debconf', inplace=True) as file:
        for line in file:
            print(line.replace("keyboard-configuration	keyboard-configuration/xkb-keymap	select	gb", f"keyboard-configuration	keyboard-configuration/xkb-keymap	select	{keymap}")
                .replace("keyboard-configuration  keyboard-configuration/variant  select  English (UK)", f"keyboard-configuration  keyboard-configuration/variant  select  {layout}"), end='')


def _build_image(hostname):
    """Build image using docker method"""
    with open('pi-gen/config', "w") as f:
        f.write(f'IMG_NAME={hostname}\n')
        f.write(f'HOSTNAME={hostname}\n')

    [touch(it) for it in ['pi-gen/stage3/SKIP', 'pi-gen/stage4/SKIP', 'pi-gen/stage5/SKIP']]
    [touch(it) for it in ['pi-gen/stage4/SKIP_IMAGES', 'pi-gen/stage5/SKIP_IMAGES']]

    log.debug('starting image building')
    with subprocess.Popen('./build-docker.sh', cwd='pi-gen', shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
            universal_newlines=True) as proc:
        for line in proc.stdout:
            log.debug(line.rstrip())

        exit_code = proc.wait()
        if exit_code != 0:
            stderr = ", ".join(map(lambda s: s.rstrip(), proc.stderr.readlines()))
            log.error(f"image building failed with error code {exit_code} " \
                f"and stderr: {stderr}")
            raise ConfiguratorError(f'Cannot build image, check logs for details')


def touch(path):
    with open(path, 'a'):
        os.utime(path, None)


def _copy_artifacts():
    shutil.copytree('pi-gen/deploy', './artifacts')


def _clean_up():
    pass
    shutil.rmtree('pi-gen')


def query_yes_no(question: str, default: str="yes") -> bool:
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        choice = input(question + prompt).lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


if __name__ == '__main__':
    main()

import os
import shutil
import signal
import subprocess
import sys
import zipfile
from collections import OrderedDict

JUDGELS_BASE_DIR = os.environ['JUDGELS_BASE_DIR']

JUDGELS_APPS = OrderedDict(sorted({
    'jophiel'    : 9001,
    'sandalphon' : 9002,
    'sealtiel'   : 9003,
    'uriel'      : 9004,
    'michael'    : 9005,
    'jerahmeel'  : 9006
}.items(), key=lambda e: e[1]))

JUDGELS_REPOS = OrderedDict(sorted({
    'gabriel'            : {'gabriel-commons', 'moe', 'sealtiel-commons'},
    'gabriel-commons'    : {'judgels-commons'},
    'jerahmeel'          : {'sandalphon-commons', 'jophiel-commons'},
    'jophiel'            : {'jophiel-commons'},
    'jophiel-commons'    : {'play-commons'},
    'judgels'            : set(),
    'judgels-commons'    : set(),
    'michael'            : {'play-commons'},
    'moe'                : set(),
    'play-commons'       : {'judgels-commons'},
    'sandalphon'         : {'sandalphon-commons', 'jophiel-commons'},
    'sandalphon-commons' : {'play-commons', 'gabriel-commons', 'sealtiel-commons'},
    'sealtiel'           : {'play-commons', 'sealtiel-commons'},
    'sealtiel-commons'   : {'judgels-commons'},
    'uriel'              : {'uriel-commons', 'sandalphon-commons', 'jophiel-commons'},
    'uriel-commons'      : {'play-commons'}
}.items(), key=lambda e: e[0]))

JUDGELS_REPOS['--all'] = set(JUDGELS_REPOS.keys())


def die(message):
    print('[ERROR] {}'.format(message))
    sys.exit(1)


def check_output(command, working_dir):
    p = subprocess.Popen(command.split(), cwd=working_dir, stdout=subprocess.PIPE)
    return p.communicate()[0]


def execute(command, working_dir):
    try:
        subprocess.Popen(command.split(), cwd=working_dir).wait()
    except KeyboardInterrupt:
        pass


def read_file_to_string(file):
    with open(file) as f:
        return f.readlines()[0].strip()
    return None


def write_string_to_file(string, file):
    with open(file, 'w') as f:
        f.write('{}\n'.format(string))


def repo_exists(repo):
    return os.path.isdir(get_repo_dir(repo))


def assert_repo_known(repo):
    if repo not in JUDGELS_REPOS:
        die('Judgels repository judgels-{} unknown'.format(repo))


def assert_repo_clean(repo):
    if check_output('git status --porcelain --untracked-files=no', get_repo_dir(repo)):
        die('Git repository {} not clean'.format(get_repo_name(repo)))


def assert_repo_and_all_deps_clean(repo):
    for rep in get_repo_and_all_deps(repo):
        if repo_exists(rep):
            assert_repo_clean(rep)


def assert_app_known(app):
    if app not in JUDGELS_APPS:
        die('Judgels app {} unknown'.format(app))


def assert_repo_exists(repo):
    if not repo_exists(repo):
        die('Git repository {} not exist in {}'.format(get_repo_name(repo), JUDGELS_BASE_DIR))


def get_repo_dir(repo):
    if repo == 'judgels':
        return '{}/judgels'.format(JUDGELS_BASE_DIR)
    else:
        return '{}/judgels-{}'.format(JUDGELS_BASE_DIR, repo)


def get_repo_name(repo):
    return 'judgels' if repo == 'judgels' else 'judgels-{}'.format(repo)


def get_repo_and_all_deps(repo):
    deps = {repo}
    for dep in JUDGELS_REPOS[repo]:
        deps |= get_repo_and_all_deps(dep)

    deps.discard('--all')
    return deps


def get_app_pid_file(app):
    return '{}/dist/judgels-{}.pid'.format(JUDGELS_BASE_DIR, app)


def get_app_pid(app):
    if os.path.isfile(get_app_pid_file(app)):
        return int(read_file_to_string(get_app_pid_file(app)))
    else:
        return None


def clean(repo):
    assert_repo_known(repo)

    for rep in get_repo_and_all_deps(repo):
        if repo_exists(rep):
            print('Cleaning judgels-{}...'.format(rep))
            execute('./activator clean', get_repo_dir(rep))
            print()


def dist(repo):
    assert_repo_known(repo)
    assert_repo_exists(repo)

    clean(repo)

    repo_version = read_file_to_string('{}/version.properties'.format(get_repo_dir(repo)))

    execute('./activator dist', get_repo_dir(repo))

    dist_zip = '{}/target/universal/{}-{}.zip'.format(get_repo_dir(repo), repo, repo_version)
    dist_dest_dir = '{}/dist'.format(JUDGELS_BASE_DIR)

    os.makedirs(dist_dest_dir, exist_ok=True)
    shutil.copy(dist_zip, dist_dest_dir)
    zipfile.ZipFile(dist_zip).extractall(dist_dest_dir)
    os.chmod('{}/{}-{}/bin/{}'.format(dist_dest_dir, repo, repo_version, repo), 0o755)


def kill(app):
    assert_app_known(app)

    pid = get_app_pid(app)

    if pid:
        os.kill(pid, signal.SIGKILL)
        os.remove(get_app_pid_file(app))
    else:
        die('Judgels app {} not running in start mode'.format(app))


def pull(repo):
    assert_repo_known(repo)
    assert_repo_and_all_deps_clean(repo)

    for rep in get_repo_and_all_deps(repo):
        if repo_exists(rep):
            print('Pulling judgels-{}...'.format(rep))
            execute('git pull --rebase origin master', get_repo_dir(rep))
            print()
        else:
            execute('git clone https://github.com/ia-toki/judgels-{}.git'.format(rep), JUDGELS_BASE_DIR)


def push(repo):
    assert_repo_known(repo)
    assert_repo_and_all_deps_clean(repo)

    for rep in get_repo_and_all_deps(repo):
        if repo_exists(rep):
            print('Pushing judgels-{}...'.format(rep))
            execute('git push origin master', get_repo_dir(rep))
            print()


def release(version):
    repos = set(JUDGELS_REPOS.keys())
    repos.discard('--all')

    for repo in repos:
        assert_repo_exists(repo)
        assert_repo_clean(repo)

    for repo in repos:
        print('Bumping {}...'.format(get_repo_name(repo)))

        write_string_to_file(version, '{}/version.properties'.format(get_repo_dir(repo)))
        execute('git add version.properties', get_repo_dir(repo))
        execute('git commit -m "Bump version {}"'.format(version), get_repo_dir(repo))
        execute('git tag -a v{} -m "Version {}"'.format(version, version), get_repo_dir(repo))
        execute('git push --tags origin master'.format(version, version), get_repo_dir(repo))
        print()


def run(app, port):
    assert_app_known(app)
    assert_repo_exists(app)

    if port == -1:
        port = JUDGELS_APPS[app]

    execute('./activator run -Dhttp.port={}'.format(port), get_repo_dir(app))


def start(app, version, port):
    assert_app_known(app)

    if port == -1:
        port = JUDGELS_APPS[app]

    command = 'bin/{}'.format(app) + \
              ' -Dpidfile.path=../judgels-{}.pid'.format(app) + \
              ' -Dhttp.port={}'.format(port)
    execute(command, '{}/dist/{}-{}'.format(JUDGELS_BASE_DIR, app, version))


def start_https(app, version, port):
    assert_app_known(app)
    assert_repo_exists(app)

    if port == -1:
        port = JUDGELS_APPS[app]

    command = 'bin/{}'.format(app) + \
              ' -Dpidfile.path=../judgels-{}.pid'.format(app) + \
              ' -Dhttp.port=disabled -Dhttps.port={}'.format(port)
    execute(command, '{}/dist/{}-{}'.format(JUDGELS_BASE_DIR, app, version))


def status():
    print('=================================================================')
    print('                        JUDGELS STATUS                           ')
    print('=================================================================')
    print()

    for app in JUDGELS_APPS:
        print('{}: {}'.format(app, 'RUNNING' if get_app_pid(app) else 'STOPPED'))

    print()
    print('=================================================================')

def main():
    if len(sys.argv) < 2:
        die('Usage: judgels <command>')

    command = sys.argv[1]

    if command == 'clean':
        if len(sys.argv) != 3:
            die('Usage: judgels clean <repo>')

        clean(sys.argv[2])

    elif command == 'dist':
        if len(sys.argv) != 3:
            die('Usage: judgels dist <repo>')

        dist(sys.argv[2])

    elif command == 'kill':
        if len(sys.argv) != 3:
            die('Usage: judgels kill <app>')

        kill(sys.argv[2])

    elif command == 'pull':
        if len(sys.argv) != 3:
            die('Usage: judgels pull <repo>')

        pull(sys.argv[2])

    elif command == 'push':
        if len(sys.argv) != 3:
            die('Usage: judgels push <repo>')

        push(sys.argv[2])

    elif command == 'release':
        if len(sys.argv) != 3:
            die('Usage: judgels release <version>')

        release(sys.argv[2])

    elif command == 'run':
        if len(sys.argv) < 3 or len(sys.argv) > 4:
            die('Usage: judgels run <app> [port]')

        if len(sys.argv) == 3:
            run(sys.argv[2], -1)
        else:
            run(sys.argv[2], sys.argv[3])

    elif command == 'start':
        if len(sys.argv) < 4 or len(sys.argv) > 5:
            die('Usage: judgels start <app> <version> [port]')

        if len(sys.argv) == 4:
            start(sys.argv[2], sys.argv[3], -1)
        else:
            start(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == 'start-https':
        if len(sys.argv) < 4 or len(sys.argv) > 5:
            die('Usage: judgels start-https <app> <version> [port]')

        if len(sys.argv) == 4:
            start_https(sys.argv[2], sys.argv[3], -1)
        else:
            start_https(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == 'status':
        if len(sys.argv) != 2:
            die('Usage: judgels status')

        status()

    else:
        die('Unrecognized judgels command: {}'.format(sys.argv[1]))


if __name__ == '__main__':
    main()

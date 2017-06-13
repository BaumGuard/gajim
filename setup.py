#!/usr/bin/env python3

import os
import sys

if sys.version_info[0] < 3:
    sys.exit('Tried to install with Python 2, gajim only supports Python 3.')

import codecs

from setuptools import setup, find_packages
# from distutils.core import setup
from distutils import log
from distutils.command.build import build as _build
#from distutils.command.install import install as _install
#from setuptools.command.build_py import build_py as _build # build_dir is unknown
from distutils.util import convert_path, newer

import gajim

pos = [x for x in os.listdir('po') if x[-3:] == ".po"]
ALL_LINGUAS = sorted([os.path.split(x)[-1][:-3] for x in pos])

def build_trans(build_cmd):
    '''
    Translate the language files into gajim.mo
    '''
    data_files = build_cmd.distribution.data_files
    for lang in ALL_LINGUAS:
        po_file = os.path.join('po', lang + '.po')
        mo_file = os.path.join(build_cmd.build_base, 'mo', lang, 'LC_MESSAGES',
                               'gajim.mo')
        mo_file_unix = (build_cmd.build_base + '/mo/' + lang +
                        '/LC_MESSAGES/gajim.mo')
        mo_dir = os.path.dirname(mo_file)
        if not(os.path.isdir(mo_dir) or os.path.islink(mo_dir)):
            os.makedirs(mo_dir)

        if newer(po_file, mo_file):
            cmd = 'msgfmt %s -o %s' % (po_file, mo_file)
            if os.system(cmd) != 0:
                os.remove(mo_file)
                msg = 'ERROR: Building language translation files failed.'
                ask = msg + '\n Continue building y/n [n] '
                reply = input(ask)
                if reply in ['n', 'N']:
                    raise SystemExit(msg)
            log.info('Compiling %s >> %s', po_file, mo_file)

        #linux specific piece:
        target = 'share/locale/' + lang + '/LC_MESSAGES'
        data_files.append((target, [mo_file_unix]))

def build_man(build_cmd):
    '''
    Compresses Gajim manual files
    '''
    data_files = build_cmd.distribution.data_files
    for man in ['gajim.1', 'gajim-history-manager.1', 'gajim-remote.1']:
        filename = os.path.join('data', man)
        newdir = os.path.join(build_cmd.build_base, 'man')
        if not(os.path.isdir(newdir) or os.path.islink(newdir)):
            os.makedirs(newdir)

        import gzip
        man_file_gz = os.path.join(newdir, man + '.gz')
        if os.path.exists(man_file_gz):
            if newer(filename, man_file_gz):
                os.remove(man_file_gz)
            else:
                filename = False

        if filename:
            #Binary io, so open is OK
            with open(filename, 'rb') as f_in,\
                    gzip.open(man_file_gz, 'wb') as f_out:
                f_out.writelines(f_in)
                log.info('Compiling %s >> %s', filename, man_file_gz)

        src = build_cmd.build_base  + '/man' + '/' + man + '.gz'
        target = 'share/man/man1'
        data_files.append((target, [src]))

def build_intl(build_cmd):
    '''
    Merge translation files into desktop and mime files
    '''
    data_files = build_cmd.distribution.data_files
    base = build_cmd.build_base

    merge_files = (('data/org.gajim.Gajim.desktop', 'share/applications', '-d'),
                   ('data/gajim-remote.desktop', 'share/applications', '-d'),
                   ('data/org.gajim.Gajim.appdata.xml', 'share/metainfo', '-x'))

    for filename, target, option in merge_files:
        filenamelocal = convert_path(filename)
        newfile = os.path.join(base, filenamelocal)
        newdir = os.path.dirname(newfile)
        if not(os.path.isdir(newdir) or os.path.islink(newdir)):
            os.makedirs(newdir)
        merge(filenamelocal + '.in', newfile, option)
        data_files.append((target, [base + '/' + filename]))

def substitute_variables(filename_in, filename_out, subst_vars):
    '''
    Substitute variables in a file.
    '''
    f_in = codecs.open(filename_in, encoding='utf-8')
    f_out = codecs.open(filename_out, encoding='utf-8', mode='w')
    for line in f_in:
        for variable, substitution in subst_vars:
            line = line.replace(variable, substitution)
        f_out.write(line)
    f_in.close()
    f_out.close()


def merge(in_file, out_file, option, po_dir='po', cache=True):
    '''
    Run the intltool-merge command.
    '''
    option += ' -u'
    if cache:
        cache_file = os.path.join('po', '.intltool-merge-cache')
        option += ' -c ' + cache_file

    if (not os.path.exists(out_file) and os.path.exists(in_file)):
        if sys.platform == 'win32':
            cmd = (('set LC_ALL=C && perl -S intltool-merge %(opt)s %(po_dir)s %(in_file)s '
                '%(out_file)s') %
              {'opt' : option,
               'po_dir' : po_dir,
               'in_file' : in_file,
               'out_file' : out_file})
        else:
            cmd = (('LC_ALL=C intltool-merge %(opt)s %(po_dir)s %(in_file)s '
                '%(out_file)s') %
              {'opt' : option,
               'po_dir' : po_dir,
               'in_file' : in_file,
               'out_file' : out_file})
        if os.system(cmd) != 0:
            msg = ('ERROR: %s was not merged into the translation files!\n' %
                    out_file)
            raise SystemExit(msg)
        log.info('Compiling %s >> %s', in_file, out_file)


class build(_build):
    def run(self):
        build_trans(self)
        if not sys.platform == 'win32':
            build_man(self)
            build_intl(self)
        _build.run(self)


package_data_emoticons = ['data/emoticons/*/emoticons_theme.py',
                          'data/emoticons/*/*.png',
                          'data/emoticons/*/LICENSE']
package_data_gui = ['data/gui/*.ui']
package_data_icons = ['data/icons/hicolor/*/*/*.png']
package_data_iconsets = ['data/iconsets/*/*/*.png']
package_data_style = ['data/style/gajim.css']
package_data = (package_data_emoticons
                + package_data_gui
                + package_data_icons
                + package_data_iconsets
                + package_data_style)


# only install subdirectories of data
data_files_app_icon = [
        ("share/icons/hicolor/64x64/apps", ["icons/hicolor/64x64/apps/org.gajim.Gajim.png"]),
        ("share/icons/hicolor/128x128/apps", ["icons/hicolor/128x128/apps/org.gajim.Gajim.png"]),
        ("share/icons/hicolor/scalable/apps", ["icons/hicolor/scalable/apps/org.gajim.Gajim.svg"])
    ]

data_files = data_files_app_icon


setup(
    name = "gajim",
    description = 'TODO',
    version=gajim.__version__,
    url = 'https://gajim.org',
    cmdclass = {
        'build': build, # if setuptools use "'build_py': build"
    },
    # TODO fix tests
    # TODO configure_file defs.py.in
    # TODO #install plugins
    scripts = [
        'scripts/gajim',
        'scripts/gajim-history-manager',
        'scripts/gajim-remote' ],
    packages = find_packages(),
    package_data = {'gajim': package_data},
    data_files = data_files,
)

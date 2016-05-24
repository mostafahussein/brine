#!/usr/bin/env python

import os
import json
import textwrap
import string
import sys

class Template(object):
    """
    This is a helper template class to help us render strings.
    """

    def __init__(self, source):
        dedented = textwrap.dedent(source)
        self.tmpl = string.Template(dedented.lstrip())

    def render(self, **ctx):
        return self.tmpl.substitute(**ctx)

class BrineError(Exception):
    pass

# links to Salt documentation that we will use to enhance the statefile
DOC_URLS = {
    'includes': "http://docs.saltstack.com/en/latest/ref/states/include.html",
    'packages':  "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.pkg.html",
    'files': "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.file.html",
    'services': "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.service.html",
    'cronjobs': "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.cron.html",
    'commands': "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.cmd.html",
    'sysctl' : "http://docs.saltstack.com/en/latest/ref/states/all/salt.states.sysctl.html",
}

# some useful template fragments
TEMPLATES = {
    'module_header': Template("""
        ##
        ##  ${module}
        ##    ${doc_link}
        """),

    'map_import': Template("""{% from "${jinja_import_path}" import ${jinja_import_name} with context %}\n\n"""),

    'file_managed': Template("""
        ${state}_${name}_file:
          file.managed:
            - name: ${name}
            - source: salt://${path}/files${name}.jinja
            - template: jinja
            - makedirs: True
            - mode: '${mode}'
            - user: root
            - group: root
        """),

    'file_symlink': Template("""
        ${state}_${linkname}_link:
          file.symlink:
            - name: ${linkname}
            - target: ${targetname}
            - force: True
            - makedirs: True
            - mode: '0644'
            - user: root
            - group: root
        """),

    'file_directory': Template("""
        ${state}_${name}_dir:
          file.directory:
            - name: ${name}
            - makedirs: True
            - mode: '0755'
            - user: root
            - group: root
        """),

    'file_absent': Template("""
        ${state}_${name}_${filedir}:
          file.absent:
            - name: ${name}
        """),

    'pkg_installed': Template("""
        ${state}_${pkg}_pkg:
          pkg.installed:
            - name: ${pkg}
        """),

    'pkg_installed_with_version': Template("""
        ${state}_${pkg}_pkg:
          pkg.installed:
            - name: ${pkg}
            - version: {{ versions['${pkg}'] }}
            - refresh: True
        """),

    'pkg_removed': Template("""
        remove_${state}_${pkg}_pkg:
          pkg.removed:
            - name: ${pkg}
        """),

    'pkg_removed_with_version': Template("""
        ${state}_${pkg}_pkg:
          pkg.removed:
            - name: ${pkg}
            - version: {{ versions['${pkg}'] }}
        """),

    'service_running': Template("""
        ${state}_${svc}_svc:
          service.running:
            - name: ${svc}
            - enable: True
        """),

    'service_dead': Template("""
        stop_${state}_${svc}_svc:
          service.dead:
            - name: ${svc}
            - enable: False
        """),

    'cmd_run': Template("""
        run_${state}_${title}_cmd:
          cmd.run:
            - name: ${cmd}
        """),

    'cmd_script': Template("""
        run_${state}_${title}_script:
          cmd.script:
            - name: ${script}
        """),

    'sysctl_present': Template("""
        {% for setting, value in sysctl.items() %}
        ${state}_{{ setting }}:
          sysctl.present:
            - name: {{ setting }}
            - value: {{ value }}
            - config: /etc/sysctl.conf
        {% endfor %}
        """),

    'cron_present': Template("""
        ${state}_${command}_conjob:
          cron.present:
            - name: ${command}
            - user: ${user} 
            - minute: ${minute}
            - hour: ${hour}
            - daymonth: ${dayofmonth}
            - month: ${month}
            - dayweek: ${dayofweek}
        """),
}


class Brine(object):
    """
    Example usage:

        brine = Brine()
        brine.load()
        brine.save()
    """

    def __init__(self):
        self.parsed = dict()
        self.statename = None
        self.prefix = ''
        self.versions_map = dict()
        self.file_name = dict()
        self.file_content = dict()

    def load(self, filename='Brinefile', **kwargs):

        with open(filename, 'r') as fp:
            self.parsed = self._parse_brinefile(fp)

        if 'rolename' in self.parsed:
            self.statename = self.parsed['rolename'][0]
            self.prefix = 'role'
        elif 'elementname' in self.parsed:
            self.statename = self.parsed['elementname'][0]
            self.prefix = 'element'

        if not self.statename:
            raise BrineError('Brinefile is missing required section. Choose one of: %rolename, %elementname')

        self.path = os.path.join(self.prefix, self.statename.replace('.', '/'))
        self.files_dir = kwargs.get('files_dir', 'files')
        self.maps_dir = kwargs.get('maps_dir', 'maps')
        self.sls_file = kwargs.get('sls_file', 'init.sls')
        self.pillar_example = kwargs.get('pillar_example', 'pillar.example')
        self.formula_file = kwargs.get('formula_file', 'FORMULA')
        self.readme_file = kwargs.get('readme_file', 'README.md')
        self.versions_map_file = os.path.join(self.maps_dir, "versions.map.jinja")
        self.sysctl_map_file = os.path.join(self.maps_dir, "sysctl.map.jinja")

        if self.has_package_with_version() or self.has_sysctl_with_value():
            if not os.path.exists(self.maps_dir):
                os.makedirs(self.maps_dir)

        if self.has_section('files'):
            if not os.path.exists(self.files_dir):
                os.makedirs(self.files_dir)

        self.file_name = {
            'sls': self.sls_file,
            'readme': self.readme_file,
            'versions_map': self.versions_map_file,
            'sysctl_map': self.sysctl_map_file,
            'pillar_example': self.pillar_example,
            'formula_file': self.formula_file,
        }

        self.file_content = {
            'sls': self.generate_sls(),
            'readme': self.generate_readme(),
            'versions_map': self.generate_versions_map(),
            'sysctl_map': self.generate_sysctl_map(),
            'pillar_example': self.pillar_example,
            'formula_file': self.formula_file, 
        }


    def _parse_brinefile(self, fp):
        key = None
        parsed = dict()
        for line in fp:
            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue
            elif line[0] == '%':
                key = line[1:]
                parsed[key] = []
            elif key:
                parsed[key].append(line)
        return parsed

    def save_files(self):
        self._save('sls')
        self._save('readme')
        self._save('versions_map')
        self._save('sysctl_map')

    def _save(self, kind):
        filename = self.file_name[kind]
        content = self.file_content[kind]
        if content:
            with open(filename, 'w') as fp:
                fp.write(content)

    def generate_readme(self):
        if 'description' not in self.parsed:
            return None
        tmpl = Template("""
        **${statename}**
        ====
        *${description}*

        ${readme}

        created with a little help from [Brine](https://github.com/openx/brine)
            """)
        d = '\n'.join(self.parsed['description'])
        r = ''
        if 'readme' in self.parsed:
            d += ''
            r = '\n'.join(self.parsed['readme'])
        return tmpl.render(statename=self.statename, description=d, readme=r)

    def generate_sls(self):
        sections = [
            self.sls_header(),
            self.section_versions_map_import(),
            self.section_sysctl_map_import(),
            self.section_header('includes'),
            self.section_includes(),
            self.section_header('sysctl'),
            self.section_sysctl(),
            self.section_header('packages'),
            self.section_packages(),
            self.section_header('files', extra=['directories']),
            self.section_directories(),
            self.section_files(),
            self.section_symlinks(),
            self.section_header('services'),
            self.section_services(),
            self.section_header('commands', extra=['scripts']),
            self.section_commands(),
            self.section_scripts(),
            self.section_header('cronjobs'),
            self.section_cronjobs(),
        ]
        return '\n'.join(sec for sec in sections if sec)


    def sls_header(self):
        tmpl = Template("""
            #
            # ${statename}
            #
            ${description}
            #

            """)
        if 'description' not in self.parsed:
            raise BrineError('Brinefile is missing required section %description')
        d = '\n'.join('#   {0}'.format(line) for line in self.parsed['description'])
        return tmpl.render(statename=self.statename, description=d)


    def has_section(self, name):
        return len(self.parsed.get(name, [])) > 0

    def has_sections(self, *names):
        return any(self.has_section(name) for name in names)

    def section_items(self, name):
        """
        Use this generator to iterate through the items in the named section.
        """
        items = self.parsed.get(name, [])
        for item in items:
            # first character is a potential modifier
            mod = '' if item[0] != '-' else '-'
            yield mod, item[len(mod):]


    def section_header(self, name, extra=None):
        """
        Generate the section header for the named section.
        """
        lines = []
        extra = [] if (extra is None) else extra
        if self.has_section(name) or self.has_sections(*extra):
            lines.append(TEMPLATES['module_header'].render(module=name.upper(), doc_link=DOC_URLS[name]))
        return '\n'.join(lines)


#--- includes

    def section_includes(self):
        lines = []
        if self.has_section('includes'):
            lines.append("include:")
            for include in self.parsed['includes']:
                lines.append("  - {0}".format(include))
            lines.append("\n")
        return '\n'.join(lines)

#--- packages

    def generate_versions_map(self):
        tmpl = Template("""
            {% set versions = salt["grains.filter_by"]({
                "dev": {
                    ${name_version_list}
                },
                "devint": {
                    ${name_version_list}
                },
                "qa": {
                    ${name_version_list}
                },
                "staging": {
                    ${name_version_list}
                },
                "prod": {
                    ${name_version_list}
                },
            },
            grain="environment",
            default="prod")
            %}""")
        name_version_list = []
        for item in self.package_items():
            if item['pkgversion']:
                name_version_list.append('"{pkgname}": "{pkgversion}",'.format(**item))
        if name_version_list:
            indent = ' ' * 8
            name_version_list = ('\n' + indent).join(name_version_list)
            return tmpl.render(name_version_list=name_version_list)
        return None

    def section_versions_map_import(self):
        if self.has_package_with_version():
            jinja_import_path = os.path.join(self.path, self.versions_map_file)
            jinja_import_name = os.path.basename(self.versions_map_file).split(".")[0]
            return TEMPLATES['map_import'].render(jinja_import_path=jinja_import_path, jinja_import_name=jinja_import_name)
        return None


    def has_package_with_version(self):
        return any(('=' in pkg) for pkg in self.parsed.get('packages', []))


    def package_items(self):
        """
        Use this generator to iterate through the packages in the package section.
        """
        for mod, pkg in self.section_items('packages'):
            pkgname, pkgversion = pkg, ''
            if '=' in pkg:
                pkgname, pkgversion = pkg.split('=')
            yield dict(mod=mod, pkg=pkg, pkgname=pkgname, pkgversion=pkgversion)


    def section_packages(self):
        lines = []
        for item in self.package_items():
            if item['pkgversion']:
                if item['mod'] != '-':
                    tmpl = TEMPLATES['pkg_installed_with_version']
                else:
                    tmpl = TEMPLATES['pkg_removed_with_version']
            else:
                if item['mod'] != '-':
                    tmpl = TEMPLATES['pkg_installed']
                else:
                    tmpl = TEMPLATES['pkg_removed']
            lines.append(tmpl.render(state=self.statename, pkg=item['pkgname']))
        return '\n'.join(lines)

#--- files, directories, symlinks (these should all be under the ## FILES section header)

    def file_items(self):
        for mod, filename in self.section_items('files'):
            filename, filemode = filename, '0644'
            if '=' in filename:
                filename, filemode = filename.split('=');

            yield dict(mod=mod, filename=filename, filemode=filemode)

    def section_files(self):
        lines = []
        for item in self.file_items():
            if item['mod'] != '-':
                path = os.path.join(self.prefix, self.statename.replace('.', '/'))
                lines.append(TEMPLATES['file_managed'].render(state=self.statename, path=path, name=item['filename'], mode=item['filemode']))
            else:
                lines.append(TEMPLATES['file_absent'].render(state=self.statename, name=item['filename'], filedir='file'))
        return '\n'.join(lines)


    def section_directories(self):
        lines = []
        for mod, dirname in self.section_items('directories'):
            if mod != '-':
                lines.append(TEMPLATES['file_directory'].render(state=self.statename, name=dirname))
            else:
                lines.append(TEMPLATES['file_absent'].render(state=self.statename, name=dirname, filedir='dir'))
        return '\n'.join(lines)

    def has_link_with_target(self):
        return any(('->' in link) for link in self.parsed.get('symlinks', []))

    def link_items(self):
        """
        Use this generator to iterate through the links in the %symlinks section.
        """
        for mod, link in self.section_items('symlinks'):
            linkname, targetname = link, ''
            if '->' in link:
                linkname, targetname = link.split('->')
            yield dict(mod=mod, link=link, linkname=linkname, targetname=targetname)

    def section_symlinks(self):
        lines = []
        for item in self.link_items():
            #if item['targetname']:
            if 'targetname' in item:
                if item['mod'] != '-':
                    tmpl = TEMPLATES['file_symlink']
                else:
                    tmpl = TEMPLATES['file_absent']
                lines.append(tmpl.render(state=self.statename, linkname=item['linkname'], targetname=item['targetname']))
            else:
                raise BrineError('{} in %symlinks section does not have target. Use "linkname->targetname" to point your link to your target'.format(item))
        return '\n'.join(lines)

#--- sysctl

    def has_sysctl_with_value(self):
        return any(('=' in sysctl) for sysctl in self.parsed.get('sysctl', []))

    def section_sysctl_map_import(self):
        if self.has_sysctl_with_value():
            jinja_import_path = os.path.join(self.path, self.sysctl_map_file)
            jinja_import_name = os.path.basename(self.sysctl_map_file).split(".")[0]
            return TEMPLATES['map_import'].render(jinja_import_path=jinja_import_path, jinja_import_name=jinja_import_name)
        return None

    def sysctl_items(self):
        """
        Use this generator to iterate through the links in the %sysctl section.
        """
        for mod, sysctl in self.section_items('sysctl'):
            sysctlsetting, sysctlvalue = sysctl, ''
            if '=' in sysctl:
                sysctlsetting, sysctlvalue = sysctl.split('=')
            yield dict(mod=mod, sysctl=sysctl, sysctlsetting=sysctlsetting, sysctlvalue=sysctlvalue)

    def generate_sysctl_map(self):
        tmpl = Template("""
            {% set sysctl = salt["grains.filter_by"]({
                "dev": {
                    ${setting_value_list}
                },
                "devint": {
                    ${setting_value_list}
                },
                "qa": {
                    ${setting_value_list}
                },
                "staging": {
                    ${setting_value_list}
                },
                "prod": {
                    ${setting_value_list}
                },
            },
            grain="environment",
            default="prod")
            %}""")
        setting_value_list = []
        for item in self.sysctl_items():
            if item['sysctl']:
                setting_value_list.append('"{sysctlsetting}": "{sysctlvalue}",'.format(**item))
        if setting_value_list:
            indent = ' ' * 8
            setting_value_list = ('\n' + indent).join(setting_value_list)
            return tmpl.render(setting_value_list=setting_value_list)
        return None

    def section_sysctl(self):
        lines = set()
        for item in self.sysctl_items():
            if 'sysctlvalue' in item:
                if item['mod'] != '-':
                    tmpl = TEMPLATES['sysctl_present']
                    lines.add(tmpl.render(state=self.statename))
                else:
                    return None
            else:
                raise BrineError('{} in %sysctl section does not have a value. Use "sysctlsetting=sysctlvalue" to set value'.format(item))
        return '\n'.join(lines)

#--- services

    def section_services(self):
        lines = []
        for mod, service in self.section_items('services'):
            if mod != '-':
                lines.append(TEMPLATES['service_running'].render(state=self.statename, svc=service))
            else:
                lines.append(TEMPLATES['service_dead'].render(state=self.statename, svc=service))
        return '\n'.join(lines)

#--- commands, scripts (these should all be under the ## COMMANDS section header)

    def section_commands(self):
        lines = []
        for mod, cmd in self.section_items('commands'):
            lines.append(TEMPLATES['cmd_run'].render(state=self.statename, cmd=cmd, title=cmd.split()[0]))
        return '\n'.join(lines)

    def section_scripts(self):
        lines = []
        for script in self.section_items('scripts'):
            lines.append(TEMPLATES['cmd_script'].render(state=self.statename, script=script[1], title=script[1]))
        return '\n'.join(lines)
#--- cronjobs

    def section_cronjobs(self):
        lines = []
        for mod, cron in self.section_items('cronjobs'):
            parts = cron.split()
            minute, hour, dayofmonth, month, dayofweek, user = parts[0:6]
            command = ' '.join(parts[6:])
            lines.append(TEMPLATES['cron_present'].render(state=self.statename, minute=minute, hour=hour, dayofmonth=dayofmonth, month=month, dayofweek=dayofweek, command=command, user=user))
        return '\n'.join(lines)

def main():
    brine = Brine()
    try:
        brine.load('Brinefile')
    except BrineError as e:
        sys.stderr.write("Error: {0}\n".format(e.message))
        sys.exit(1)
    brine.save_files()


if __name__ == "__main__":
    main()

**Brine**
===
Brine is a Salt Formula initializer. It allows you to express what the formula should do in the simple style and syntax of a `Brinefile`. Once you have your Brinefile filled out, you can simply run `brine.py` from within the same directory as the `Brinefile` and Brine will create all the files and directories for a "role" or "element".

Benafits of Brine
---
+ **Lower barrier to entry**   - very little knowledge of Salt's syntax or even Salt itself is required to get started making great-looking Salt Formulas.
+ **Standards and consistent** - Formula style, creation and naming of state-blocks are all formulaic and standard. 
+ **Reproducibility**          - just run `brine` again and all the files will be reproduced, just as they were originally.
+ **Easy to update**           - Because of the simplified syntax `Brinefile`s are easy to update to keep current.


Understanding Brine
===
**Brine leverages the convention of Elements and Roles in Salt. Since this is not a convention that everyone in the community has adopted, lets quickly review what these different Formula types are and what makes them different from each other.**

### _Elements_
Think of an `element` as a generic bit of configuation that might be applied to systems by being included in one or more roles. You will typically want an Element to have sane defaults and be general enough to be used accross different roles. Elements live under the `element/` directory in the root of the states files_root (i.e. `/srv/salt/element/`).

#### `Brinefile` example for element:
```
%elementname
queue.rabbitmq.server

%commands
/usr/sbin/rabbitmq-plugins enable rabbitmq_management

%files
/etc/rabbitmq/rabbitmq.config
/etc/rabbitmq/enabled_plugins

%services
rabbitmq-server

%description
installs rabbitmq and starts the service. Also, it will enable the webUI management plugin.

%readme
**WARNING: This element doesn't include the `language.erlang` element or otherwise explicitly install the `erlang package`. Make sure you include the erlang element in your role and extend the version number to the version you desire... otherwise you get whatever `erlang` package is available in repos at the time of install.**

```
### _Roles_
Roles are Formulas that define the identity of a machine. The name should be descriptive of what the machine is doing. Roles live under the `role/` directory in the root of the file file_root of your Formulas/Statefiles (i.e. `/srv/salt/role/` ).

**And... a BONUS Formula type, "_meta-role_"**
A meta role is nothing more than a role that includes other roles.

#### `Brinefile` example for role:
```
%rolename
queue.mq-service

%description
This is a simple role that will set up a rabbitmq cluster 

%files
/var/lib/rabbitmq/.erlang.cookie

%symlinks
/home->/var/home

%includes
element.queue.rabbitmq.server
element.language.erlang

%packages
nagios-plugins-check_rabbitmq

%services
# all services are started in the rabbitmq element

%sysctl
kernel.sysrq=1
net.ipv4.tcp_tw_reuse=1
```

Sections
===
Section | Description | Prepend Modifiers | Append Modifiers
------- | ----------- | ----------------- | ----------------
`%rolename`   | This sets the role name. (can not be used with `%elementname`)||
`%elementname`| Sets the name of the element. (can not be used with `%rolename`)||
`%description`| A short description used in `init.sls` comments and `README.md`||
`%readme`     | More details that will only go in the readme go here||
`%includes`   | Include elements, roles, and other sls files||
`%sysctl`     | Set sysctl.conf settings and values||
`%packages`   | Provide list of packages to be installed (or uninstalled with minus notation)|`-`| `=`
`%files`      | Provide list of files to be put in place (or to be removed with minus notation)| `-`| `=`
`%directories` | Provide list of directories to be created|`-` | `=`
`%symlinks`   | Provide list of symlinks to be created using `linkfile->targetfile`||
`%services`   | Provide list of services that should be running (or not running with minus notation)|`-`|
`%commands`   | Provide a list of commands that should be executed||
`%scripts`    | Provide a list of scripts that should be executed||
`%cronjobs`   |provide a list of cronjobs to be configured. Put these in as normal crontab entries. It will get translated to native `cron.present` state.||


Setting up Brine
===
For this to work, make sure `$HOME/bin` is in your `$PATH`
```
git clone git@github.com:openx/brine.git
cd brine
BRINE_PATH=$PWD
test -d ~/bin || mkdir ~/bin
cd ~/bin
ln -s $BRINE_PATH/brine.py brine
```

Using Brine
===
Writing a `Brinefile`
---
You will want to make a `Brinefile` in the directory where the `init.sls` will eventaully live for your role or element.
```
cd path/to/role-or-element/
touch Brinefile
vi Brinefile
```
Once you have an empty `Brinefile`, just fill it out with the sections you require. Most sections are optional, but there are a few required sections

Required sections are:
+ either `%rolename` or `%elementname`
+ `%description`

### **Package, file, directory, service negation**
To explicitly remove a file, dirctory, package, or stop a service just put a leading minus (`-`) on the line

__This would remove the `openssh` package__
```
%packages
-openssh
```
### **Specify Pacakge Versions**
In `%packages` section, you can specify a version number by using `=`

__This is how you can specify version of `openssh`__
```
%packages
openssh=6.6p1-6.3
```
By specifying the version number in the `Brinefile`, Brine will create a `maps/` directory with a `versions.map.jinja` file in it. Brine will also include that map file in the and use jinja templating to grab the version from the map file from within the `init.sls`.

### **Specify File Mode**
In `%files` section, you can specify a file mode number by using `=`. Files will default to mode `0644`

__This is how you can specify a different mode for `/etc/ssh/sshd_config`__
```
%files
/etc/ssh/sshd_config=0640
```

### **Create a Role**
To create a role, use `%rolename` in your `Brinefile`

### **Create an Element**
To create an element, use `%elementname` in your `Brinefile`


Running `brine`
---
Run `brine` in the same directory as your `Brinefile`
```
$ ls -l
total 4
-rw-r--r-- 1 drew.adams users 1149 Apr 25 13:40 Brinefile
$ brine
$ ls -l
total 12
-rw-r--r-- 1 drew.adams users 1149 Apr 25 13:40 Brinefile
drwxr-xr-x 2 drew.adams users    6 Apr 25 16:04 files
-rw-r--r-- 1 drew.adams users 2920 Apr 25 16:04 init.sls
-rw-r--r-- 1 drew.adams users  211 Apr 25 16:04 README.md
```

Known Issues/Bugs
===
[See our GitHub Issues tab, filtered by 'bug' label](https://github.com/openx/brine/issues?q=is%3Aopen+is%3Aissue+label%3Abug)


Feature Wish List
===
[See our GitHub Issues tab, filtered by 'enhancement' label](https://github.com/openx/brine/issues?q=is%3Aopen+is%3Aissue+label%3Aenhancement)

README for the FFW web app
===========================

:Authors:

    Christian Tanzer
    <tanzer@swing.co.at>

    Ralf Schlatterbeck
    <rsc@runtux.com>

The FFW web app is an application that serves data about the network
nodes deployed by www.funkfeuer.at.

It uses the `tapyr framework`_ and the `common node database`_ (CNDB).

.. _`tapyr framework`: https://github.com/Tapyr/tapyr
.. _`common node database`: https://github.com/CNDB/CNDB

System requirements
--------------------

- Linux or OS X

  * its best to set up a separate account that runs FFW

- Apache, with mod-fcgid installed

  * or another webserver, e.g. nginx...

- PostgreSQL (preferred) or mySQL

  * an account for the web app that can create databases and tables

- git

- Python (> 2.6, < 3)

  * virtualenv, distribute

  * Depending on the OS (I'm looking at you, Debian), some packages,
    e.g., werkzeug, should be installed into virtualenv to get
    versions a bit younger than a couple of years

  * This might require the installation of a build environment (for
    python packages that need the C compiler)

- Python packages

  * `Babel`_

  * `BeautifulSoup`_

  * `docutils`_

  * `flup`_

  * `jinja2`_

  * `m2crypto`_

  * `passlib`_

  * `plumbum`_

  * `psycopg2`_

  * `py-bcrypt`_

  * `pyOpenSSL`_

  * `pyasn1`_

  * `pyquery`_

  * `python-dateutil`_

  * `pytz`_

  * `rcssmin`_, `rjsmin`_ (for minimization of CSS and Javascript files)

  * `rsclib`_

  * `sqlalchemy`_

  * `werkzeug`_

  Most packages are available via the `Python Package Index`_

.. _`Babel`:           http://babel.edgewall.org/
.. _`BeautifulSoup`:   http://www.crummy.com/software/BeautifulSoup/
.. _`Python Package Index`: http://pypi.python.org/pypi
.. _`docutils`:        http://docutils.sourceforge.net/
.. _`flup`:            http://trac.saddi.com/flup
.. _`jinja2`:          http://jinja.pocoo.org/
.. _`m2crypto`:        http://pypi.python.org/pypi/M2Crypto
.. _`passlib`:         http://code.google.com/p/passlib/
.. _`plumbum`:         http://plumbum.readthedocs.org/en/latest/index.html
.. _`psycopg2`:        http://packages.python.org/psycopg2/
.. _`py-bcrypt`:       http://code.google.com/p/py-bcrypt/
.. _`pyOpenSSL`:       https://launchpad.net/pyopenssl
.. _`pyasn1`:          http://pyasn1.sourceforge.net/
.. _`pyquery`:         http://github.com/gawel/pyquery/
.. _`python-dateutil`: http://labix.org/python-dateutil
.. _`pytz`:            http://pytz.sourceforge.net/
.. _`rcssmin`:         http://opensource.perlig.de/rcssmin/
.. _`rjsmin`:          http://opensource.perlig.de/rjsmin/
.. _`rsclib`:          http://rsclib.sourceforge.net/
.. _`sqlalchemy`:      http://www.sqlalchemy.org/
.. _`werkzeug`:        http://werkzeug.pocoo.org/

Package Installation for Debian Stable aka Wheezy
--------------------------------------------------

The following is an example installation on Debian Wheezy. It contains
some information that is applicable to other distributions but is quite
Debian-specific in other parts.

If you are running in a virtual machine, you need at least 384 MB of
RAM, 256 MB isn't enough.

Some of the needed Packages are either not in Debian or are too old to
be useful. The following packages can be installed via the Debian
installer::

 $ apt-get install \
     apache2-mpm-worker build-essential git libapache2-mod-fcgid \
     postgresql python-pip python-babel python-bs4 python-dateutil \
     python-dev python-distribute python-docutils python-flup \
     python-jinja2 python-m2crypto python-openssl python-passlib \
     python-psycopg2 python-pyasn1 python-pyquery python-sqlalchemy \
     python-tz python-virtualenv python-werkzeug swig

Other packages can be installed using ``pip`` — note that you may want
to install some of these into a virtual python environment (virtualenv),
see later in sectioni `How to install`_ — depending on your
estimate how often you want to change external packages::

 $ pip install plumbum py-bcrypt rcssmin rjsmin rsclib pyspkac

Create user and database user permitted to create databases::

 $ adduser ffw
 $ createuser -d ffw -P

How to install
--------------

Assuming an account `ffw` located in /home/ffw, you'll need something
like the following::

  ### Logged in as `ffw`
  $ cd /home/ffw

  ### Define config
  $ vi .ffw.config
    ### Add the lines (using the appropriate values for **your** install)::
      cookie_salt   = 'some random value, e.g., the result of uuid.uuid4 ()'
      db_name       = "ffw"
      db_url        = "postgresql://<account>:<password>@localhost"
      languages     = "de", "en"
      locale_code   = "de"
      smtp_server   = "localhost"
      target_db_url = db_url
      time_zone     = "Mars/Olympos Mons"

  ### create a virtual environment for Python
  $ mkdir bin
  $ mkdir PVE
  $ python -m virtualenv --system-site-packages PVE/std
  $ (cd PVE ; ln -s std active)

Depending on the packages you have already installed system-wide, you
may want to install some packages into the virtual environment if you
anticipate that these will change::

  ### install Python packages into the virtualenv
  ### if one of these packages is already installed in the system
  ### Python, you'll need to say `pip install --upgrade`, not `pip install`
  $ source PVE/active/bin/activate
  $ pip install plumbum pytz py-bcrypt rcssmin rjsmin rsclib pyspkac

Then we continue with the setup of an active and a passive branch of the
web application. With this you can upgrade the passive application while
the active application is running without risking a non-functional
system should something go wrong during the upgrade::

  ### create a directory with an `active` and `passive` branch of the
  ### web application
  ###
  ### * the active branch will be the one that serves apache requests
  ###
  ### * the passive branch can be used for updating the software and
  ###   testing it. It all works will the branches can be switched
  ###

  $ mkdir fcgi
  $ mkdir v
  $ mkdir v/1
  $ mkdir v/1/www
  $ mkdir v/1/www/media
  $ ln -s v/1 active
  $ ln -s v/2 passive
  $ git clone git://github.com/Tapyr/tapyr.git v/1/tapyr
  $ git clone git://github.com/CNDB/CNDB.git   v/1/cndb
  $ git clone git://github.com/FFM/FFW.git     v/1/www/app
  $ cp -a v/1 v/2

  $ vi active/www/.ffw.config
    ### Add the lines (using the appropriate values for **your** install)::
      db_name       = "ffw1"
  $ vi passive/www/.ffw.config
      db_name       = "ffw2"

  ### Define PYTHONPATH
  $ export PYTHONPATH=/home/ffw/active/cndb:/home/ffw/active/tapyr

With a small config-file, the deploy-app can automatically create an
Apache configuration file and a fcgi script. You can find sample
config-files in active/www/app/httpd_config/. For instance,
active/www/app/httpd_config/ffw_gg32_com__443.config contains::

        config_path     = "~/fcgi/ffw_gg32_com__443.config"
        host_macro      = "gtw_host_ssl"
        port            = "443"
        script_path     = "~/fcgi/ffw_gg32_com__443.fcgi"
        server_admin    = "christian.tanzer@gmail.com"
        server_name     = "ffw.gg32.com"
        ssl_key_name    = "srvr1-gg32-com-2048"

Create a config::

  ### Create a fcgi script and config for Apache
  $ python active/www/app/deploy.py create_config \
      -HTTP_Config <your-config> -input_encoding=utf-8

You can use the created Apache configuration as is, or modify it
manually or by modifiying the template.

For Debian, the apache configuration should be placed into
``/etc/apache2/sites-available/``, e.g., into the file
``nodedb2.example.com``, and enabled. You probably will have to disable
the default site installed. We used the following commands — we
also enable some needed modules::

  $ a2ensite nodedb2.example.com
  $ a2dissite default
  $ a2enmod mod_expires
  $ a2enmod fcgid
  $ /etc/init.d/apache2 restart

For https sites, you'll also need the modules::

  $ a2enmod rewrite
  $ a2enmod ssl

Finally we create a database and populate it with data::

  ### Create a database
  $ python active/www/app/deploy.py create

  ### Put some data into the database

Whenever we need to upgrade the installation, we can update the passive
configuration, set up everything, migrate the data from the active to
the passive configuration, and if everything went OK, enable it by
exchanging the symbolic links to the active and passive configuration::

  ### Test deployment script and generate some needed files
    ### Update source code
    $ python passive/www/app/deploy.py update

    ### Byte compile python files
    $ python passive/www/app/deploy.py pycompile

    ### Compile translations
    $ python passive/www/app/deploy.py babel compile

    ### Migrate database from active to passive
    $ python passive/www/app/deploy.py migrate -Active -Passive -verbose

    ### Setup app cache
    $ python passive/www/app/deploy.py setup_cache

  ### Switch active and passive branches
  $ python passive/www/app/deploy.py switch
  $ sudo /etc/init.d/apache2 restart

Contact
-------

Christian Tanzer <tanzer@swing.co.at> and
Ralf Schlatterbeck <rsc@runtux.com>

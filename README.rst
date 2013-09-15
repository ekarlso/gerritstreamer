Installing
==========

1. Clone
    $ git clone git://github.com/ekarlso/gerritstreamer
    $ cd gerritstreamer

2. Install in development mode
    $ pip install -r requirements.txt
    $ python setup.py develop

3. Copy upstart job
    $ cp contrib/gerritstreamer.conf /etc/init

4. Copy configuration and edit the wanted files to your settings
    $ cp -Rv etc/gerritstreamer/ /etc

5. Setup ssh key and Host config for the gerrit instead
    Your ~/.ssh/config should have a entry that correponds to the host setting under the [gerrit] section like:
        host = review

        Host review
            Hostname review.openstackorg
            Username endre-karlson
            Port 29418
    This is required from PyGerrit to work.

6. Configure jobs.yaml to your liking and the [jenkins] settings.

7. Fix the log file - replace user with the same user you have configured in /etc/init/gerritstreamer.conf
    $
        touch /var/log/gerritstreamer.log
        chmod 640 /var/log/gerritstreamer.log
        chown <user> /var/log/gerritstreamer.log

7. Try starting gerritstreamer
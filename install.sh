#!/bin/sh

export DEBIAN_FRONTEND=noninteractive

SCRIPT_PATH=$(realpath $0)
SCRIPT_DIR=$(dirname $SCRIPT_PATH)

get_dep()
{
    deps=$1
    echo installing dependencies: $deps
    sudo apt-get -y install $deps
}

install_db()
{
    echo
    echo "Installing Databases..."
    get_dep sqlite3
    get_dep redis
    cd $SCRIPT_DIR/db
    if [ ! -f gauge.db ]; then
	echo -n "Creating database... "
	sqlite3 gauge.db < schema.sql
	echo "Done."
    else
	echo "Database already exists!"
    fi
}

configure_python()
{
    echo
    echo "Configuring Python."
    get_dep python3-venv
    get_dep python3-numpy
    get_dep libatlas-base-dev
    get_dep libopenjp2-7-dev
    get_dep libavcodec-dev
    get_dep libavformat-dev
    get_dep libswscale-dev
    get_dep libgtk-3-dev

    cd $SCRIPT_DIR
    
    echo -n "Creating venv..."
    python3 -m venv ~/.venv
    echo "Done."

    echo -n "Activating venv..."
    . ~/.venv/bin/activate
    echo "Done."
    
    echo "Installing modules..."
    python -m pip install redis
    python -m pip install picamera
    python -m pip install opencv-python
    python -m pip install rich
    python -m pip install Flask
    python -m pip install Flask-SQLAlchemy
    python -m pip install flask-redis
    python -m pip install Flask-HTTPAuth
    python -m pip install gunicorn
    python -m pip install gevent
    python -m pip install homeassistant-api
    python -m pip install rpi_ws281x
    python -m pip install adafruit-circuitpython-neopixel
    
    echo -n "Deactivating venv..."
    deactivate
    echo "Done."
}

setup_services()
{
    cd $SCRIPT_DIR/systemd
    sudo ./setup-services.sh remove
    sudo ./setup-services.sh install
}

setup_webapp()
{
    echo
    echo "The web app requires at least one account to be created."
    echo "Please set up an account now."
    echo
    
    cd $SCRIPT_DIR/webapp
    ./admin
}

setup_hass()
{
    cd $SCRIPT_DIR/clients
    read -p "Do you want to enable Home Assistant support (y/n)? " response
    case "$response" in
	[yY][eE][sS]|[yY])
	    echo
	    echo "The 'nano' editor will now open, allowing you to paste your Home Assistant Long-Lived Access Token."
	    echo "Be sure to not add any line endings or extra text when pasting.  Use Ctrl-X to save when done."
	    
	    VALID=0
	    while [ $VALID = 0 ]; do

		echo
		read -p "Hit enter when ready..." foo

		nano token.hass

		TOKEN_SIZE=`wc --bytes token.hass | cut -d' ' -f1`
		if [ "$TOKEN_SIZE" = "184" ]; then
		    echo
		    echo "Token is valid length."
		    VALID=1
		else
		    echo
		    echo "Token does not look valid.  Expected 184 bytes, got ${TOKEN_SIZE} bytes."
		    echo "The 'nano' editor will open again so you can fix the token.  Ctrl-C to quit this script."
		fi
	    done
		   

	    sudo systemctl enable gauge-hass

	    ;;
	*)
	    echo "Home Assistant support will be disabled."
	    sudo systemctl disable gauge-hass
	    ;;
	esac
}

install_db
configure_python
setup_services
setup_webapp
setup_hass


echo
echo "Installation complete."

# c4i2p: Crawling for I2P

HTTP crawling tool for the I2P Darknet sites.

<img src="c4i2p_modules.png" alt="c4i2p functional modules" width="60%">

Although it was originally conceived to be used for the I2P anonymous network, 
this tool can also be used for crawling some others HTTP based web sites 
like those found in TOR, Freenet and/or the surface web (see project c4darknet at https://github.com/EmilioFigueras/I2P_Crawler).

The crawler automatically extracts links to other i2p site thus getting an overall 
view of the I2P darknet inter-connections and some other useful information.

## How to install

#### Requirements

The crawler relies on the use of an adequate environment to run it. Mandatory elements
for that are:

- Linux **Unbuntu 16.04** and above (it can be run in older version)
- **I2P router** (latest version)
- **Mysql 5.7**, though some other DBMS can be used like SQLite.
- **Python 2.7** environment (+ dependencies found in requeriments.txt)

#### Installation steps
As python based tool, we recommend to use virtual environments. In the following, we are going
to use conda (https://www.anaconda.com) to create and manage python environments.

**Dabatase**
1) Download and install database management system. We choose Mysql but some other can be used.

```
sudo apt install -y mysql-server-5.7 mysql-client-5.7
```

2) Creating schema and users.

Scheme ```i2p_database```, user ```i2p``` and password ```password``` will be created after 
executing the following commands.

```
$ sudo mysql
mysql> create database i2p_database;
mysql> create user 'i2p'@'localhost' identified by 'password';
mysql> grant all privileges on `i2p_database`.* to 'i2p'@'localhost';
mysql> quit;
```

**Python environment and dependencies**

1) Creating a virtual environment.
```
$ conda create -n py27 python=2.7
$ conda activate py27
(py27) $
```
2) Installing python dependencies.
```
(py27) $ cd <root_project_folder>/crawler/
(py27) $ pip install -r requirements.txt
```

3) Database access from python.

We use pony ORM for data persistence layer, so how to connect to database must be configured.
Please edit the lien in file ```entities.py``` which is located 
in ```<root_project_folder>/crawler/database/```. Please, change the ```password``` accordingly.

```
db.bind(provider='mysql', host='localhost', user='i2p', passwd='password', db='i2p_database')
```

### Crawling
Now it is time to crawl the I2P network. Every time you want to start a new crawling procedure,
we recommend to follow the next steps.

1) Database population.

We recommend to drop and create the scheme before running the crawling for a clean and fresh running.

```
$ sudo mysql
mysql> drop database i2p_database;
mysql> create database i2p_database;
mysql> quit;
```

```
(py27) $ cd <root_project_folder>/crawler/database/
(py27) $ python populate.py
```

2) Spiders crawling output.

Spiders output JSON files in specific folders so they should already be created. 
On the contrary, please create them. For a clean and fresh running, delete all files in that folders.

```
(py27) $ cd <root_project_folder>/crawler/i2p/spiders/
(py27) $ mkdir finished ongoing
```

3) Supervising crawling procedure: log.

In order to supervise the crawling procedure, the log file is created in a specific folder.
If "logs" folder is not created, please create it. For a clean and fresh running, delete this file.

```
(py27) $ cd <root_project_folder>/
(py27) $ mkdir logs
```

4) Starting the crawling process.


```
(py27) $ cd <root_project_folder>/crawler/
(py27) $ python manager.py &> /dev/null
```

If you want to supervise the crawling procedure please use see 
```<root_project_folder>/logs/i2pcrawler.log```. Also, more information is being storage in
the database.


*Note:* The crawling procedure output tons of logs and information on standard output so we recommend to 
launch the crawler appending ```&> /dev/null``` but it is up to the user.

## Authors

* **Alberto Abellán-Galera**
* **Roberto Magán-Carrión**
* **Gabriel Maciá-Fernández**

See also the list of [contributors](https://github.com/nesg-ugr/I2P_Crawler/graphs/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE) file for details.

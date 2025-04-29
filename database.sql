-- database: g:\Taskify\New folder\tasify.db

CREATE TABLE users (uid integer NOT NULL PRIMARY KEY , 
password varchar(128) NOT NULL, 
last_login datetime NULL,
username varchar(150) NOT NULL UNIQUE,
email varchar(254) NOT NULL,
is_staff bool NOT NULL, 
date_joined datetime NOT NULL, 
isapproved int default 0);

create table admin(aid int,adminname varchar(100),adminpassword varchar(100));

create table group_id(gid int,groupname varchar(100),groupimage varchar(1000));

create table group_member(gmid int,gid int,uid int);

CREATE TABLE task (id integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
task_name varchar(255) NOT NULL, description text NOT NULL, 
priority varchar(10) NOT NULL, reminder date NOT NULL, 
created_at datetime NOT NULL, end_date date NULL,
 start_date date NULL, created_by_id integer NOT NULL,
 status varchar(100))
 ;
create table groupsdetails(gid int not null primary key,groupname varchar(1000),imageicon varchar(100));

 CREATE TABLE accounts_task_assigned_to
(id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
 task_id bigint NOT NULL , 
 user_id integer ,groupid int);

 CREATE TABLE accounts_chat (cid integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
 text varchar(100) NOT NULL, 
 trans datetime NOT NULL, 
 from_user_id integer , to_user_id integer);


 CREATE TABLE group_accounts_chat (cid integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
 text varchar(100) NOT NULL, 
 trans datetime NOT NULL, 
 from_user_id integer , to_user_id integer);


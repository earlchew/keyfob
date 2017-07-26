# Memento

Memento is a command line application that is used to remember passwords, or any other kind of secret, for a login session.
Once remembered, the password can be recalled for reuse during the session. The password is stored in memory, and does
not persist beyond the login session.

## Getting Started

The following three concepts are required to understand and use Memento:

1. The application that requires the password
1. The name used to identify the application
1. The means by which the password will be supplied to the application

For the purposes of illustration, the `openssl passwd` command can represent a useful application, and the
`-noverify -salt xx` options used to ensure repeatable results for the password _Pa55w0rd_:
```
$ openssl passwd -noverify -salt xx
Password:
xxU4b0XBMjadY
```

For illustration, the name _EXAMPLE_ will be used to identify this application, and from the manual page for
[sslpasswd(1)](https://linux.die.net/man/1/sslpasswd) the password can be supplied from a file, from stdin,
or from the terminal.

In these examples, the Memento application will be invoked three times:
1. Firstly to revoke the password stored from any previous example
1. Secondly to remember the new password on th initial invocation of the openssl instance
1. Thirdly to reinvoke a new openssl instance using the recalled password

`$ memento --revoke EXAMPLE`
`$ memento -- EXAMPLE openssl passwd -noverify -salt xx -in {}`  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ memento -- EXAMPLE openssl passwd -noverify -salt xx -in {}`  
`xxU4b0XBMjadY`

`$ memento --revoke EXAMPLE`
`$ ./memento < /dev/null --pipe -- EXAMPLE openssl passwd -noverify -salt xx -stdin`  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ ./memento < /dev/null --pipe -- EXAMPLE openssl passwd -noverify -salt xx -stdin`  
`xxU4b0XBMjadY`  

`$ memento --revoke EXAMPLE`
`$ memento --tty -- EXAMPLE openssl passwd -noverify -salt xx`  
**`Memento: ********`**  
`Password:`  
`xxU4b0XBMjadY`  
`$ memento --tty -- EXAMPLE openssl passwd -noverify -salt xx`  
`Password:`  
`xxU4b0XBMjadY`  

### Prerequisites

The current implementation will only work on Linux because of the following dependencies:

* Linux keyctl(2)
* Linux splice(2)
What things you need to install the software and how to install them

```
Give examples
```

### Installing

To install the program:

* git clone https://github.com/earlchew/memento.git
* memento/install.sh

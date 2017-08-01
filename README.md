## Introduction

Keysafe is a command line application that is used to remember passwords, or any other kind of secret, for a login session.
Once remembered, the password can be recalled for reuse during the session. The password is stored in memory, and does
not persist beyond the login session.

Typically secrets such as passwords are required during a login session to access secured services, and normally
this requires the user to provide the password each time the service is accessed. Doing so repeatedly can be
tiresome and errorprone.

The Keysafe application can be used to remember the secret in a secure way, and to provide that secret each time
the secured service is accessed for the duration of the loging session.

The remembered secret is discarded once the login session terminates, or when the secret expires. Once the secret is
discarded, reuse requires the user to re-enter the secret.

## Getting Started

### Prerequisites

* Linux keyctl(2)
* Linux splice(2)
* bash(1), sh(1), ksh(1) etc

### Installing

The Keysafe application can be run directly from the cloned git repository. To install the application in this way:

* `git clone https://github.com/earlchew/keysafe.git`
* `cd keysafe && ./install.sh`
* Optionally: `cd keysafe && ln -s ./keysafe /usr/local/bin/`

Alternatively the application can be installed in a target directory using the package manager:

* `git clone https://github.com/earlchew/keysafe.git`
* `cd keysafe && pip install -r requirements.txt .`

## Usage

### Concepts

The following three concepts are required to understand and use Keysafe:

1. The application that requires the password
1. The key used to identify the application
1. The means by which the password will be supplied to the application

For the purposes of illustration, the `openssl passwd` command can represent a useful application, and the
`-noverify -salt xx` options used to ensure repeatable results for the password _Pa55w0rd_:
```
$ openssl passwd -noverify -salt xx
Password:
xxU4b0XBMjadY
```

To keep secrets as secure possible, the Keysafe application uses the following techniques:

* Avoid writing secrets to files, and reading secrets from files
* Avoid writing secrets as command line arguments
* Avoid writing secrets to shell history
* Limit the lifetime of memorised secrets
* Memorise encrypted secrets

While these techniques do much to limit the exposure of the password in plaintext, it remains possible for
programs run by the root user, and other programs that are running under the user's own account, from
eavesdropping on channels used to transmit the password to the secured service, or examining the memory
of the client used to access the secured service.

### Usage

For illustration, the name _EXAMPLE_ will be used to identify this application, and from the manual page for
[`sslpasswd(1)`](https://linux.die.net/man/1/sslpasswd) the password can be supplied from a file, from stdin,
or from the terminal.

In these examples, the Keysafe application will be invoked three times:
1. Revoking the password from the previous example, if any
1. Remember the new password on th initial invocation of the openssl instance
1. Recall the password when invoking a new openssl instance

#### Using a File to Send Secrets

`$ keysafe --revoke EXAMPLE-$$`  
`$ keysafe EXAMPLE -- openssl passwd -noverify -salt xx -in @@`  
**`[1]+  Stopped                 keysafe EXAMPLE -- openssl passwd -noverify -salt xx -in @@`**  
**` unset _KEYSAFE_hCYju ; read -r _KEYSAFE_hCYju </proc/32143/fd/5 ; fg`**  
`$`  
`$ `**`keysafe -s <($_KEYSAFE_hCYju) EXAMPLE-2804 -- openssl passwd -noverify -salt xx -in @@`**  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ keysafe -s <($_KEYSAFE_hCYju) EXAMPLE-2804 -- openssl passwd -noverify -salt xx -in @@`  
`xxU4b0XBMjadY`  

This first example illustrates a couple of main points:
* The use of an unexported intermediate shell variable `$_KEYSAFE_hCYju` to prevents the key salt being recorded
in shell history. Inspection of shell history will only show the use of the shell variable, but will not
show the actual value being used.
* The use of process substitution at the shell `<($_KEYSAFE_hCYju)` prevents the key salt being
recorded as part of the title of the process. Inspection of the process using `ps(1)` will only show that the
salt is being read from `/dev/fd/N` or similar.
* The key name is augmented with a suffix to disambiguate it from instances used in other shell instances
in the same login session.
* While the key provides a useful mnemonic to make it easy to remember the its purpose, the addition of
of salt allows secrets to be stored securely. The revised command available at the command line (shown in **bold**
in the example). If the revised command is acceptable, the user press `<RETURN>` and proceed, otherwise the
command line is available for further editing.
* If no value was previously recorded for the key, the Keysafe application prompts the user with the word
**`Memento:`** to type the initial value.
* The command line argument `@@` is replaced by the name of the pipe over which the application can read
the secret.

The password itself is stored in a session keyring as described in [keyrings(7)](http://man7.org/linux/man-pages/man7/keyrings.7.html). The command line tool [keyctl(1)](http://man7.org/linux/man-pages/man1/keyctl.1.html):

`$ keyctl show @s`  
`Keyring`  
`1069142298 --alswrv   1021  1021  keyring: _ses`  
`1030239571 --alswrv   1021  1021   \_ user: keysafe:EXAMPLE-2804`  
`$ cat /proc/keys`  
`...`  
`d683553 I--Q---     1  59m 3f230000  1021  1021 user      keysafe:EXAMPLE-2804: 100`  
`$ keyctl print $((0x3d683553))`  
`gAAAAABZfNOm5ymrvBaxRwdHPICfJ7XDXcf95-UwYUhCIhekhR7RPoCZjc5hmKSWS1pekSGtMVY8ePH6_OT_bl4dB4ZtBpeHzA==`  

The following points are noteworthy:
* The name of the key is plain to see and can be helpful to remember its purpose.
* Without further use, the key will expire after a configurable time, or when the session terminates.
* The keyring records an encrypted version of the value that requires the salted key (`EXAMPLE@370c1e` in
this example) to decrypt.

If the wrong value was stored, the keyring can be updated with the correct value:

`$ keysafe -s <($_KEYSAFE_hCYju) -- EXAMPLE-2804`  
**`Memento: ********`**  
`$ keysafe -s <($_KEYSAFE_hCYju) -- EXAMPLE-2804 openssl passwd -noverify -salt xx -in @@`  
`xxIrpmD5YjTxs`  

#### Using Command Arguments to Send Secrets

The above examples show `sslpasswd(1)` reading a password from a file. This next example shows `sslpasswd(1)`
obtaining the password directly from the command argument:

`$ keysafe --revoke EXAMPLE-$$`  
`$ keysafe -a EXAMPLE -- openssl passwd -noverify -salt xx @@`  
**`[1]+  Stopped                 keysafe -a EXAMPLE -- openssl passwd -noverify -salt xx @@`**  
**` unset _KEYSAFE_hn3nf ; read -r _KEYSAFE_hn3nf </proc/14017/fd/5 ; fg`**  
`$`  
`$ `**`keysafe -a -s <($_KEYSAFE_hn3nf) EXAMPLE-2804 -- openssl passwd -noverify -salt xx @@`**  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ keysafe -a -s <($_KEYSAFE_hn3nf) EXAMPLE-2804 -- openssl passwd -noverify -salt xx @@`  
`xxU4b0XBMjadY`  

Under normal circumstances this is the worst of all ways to provide a password to a program:
* The password would be present on the command line in plaintext
* The password is visible on the terminal
* The password is visible process listings (eg `ps(1)`, `/proc/pid/cmdline`, etc)
* The password is visible in shell histories

Use of Keysafe mitigates these risks because the secret is tunnelled to the application program. The secret
is available to the process via its in-process command line (ie `(argc, argv)`), but the secret
is not visible on the terminal, in processing listings, nor present in shell histories.

The following demonstrates that while the program can read the password directly from its command
line argument, casual inspection by an external observer does not reveal the password:

`$ keysafe -a -s <($_KEYSAFE_hn3nf) EXAMPLE-2804 -- sh -c 'echo args: "$@" ; echo cmdline: ; tr "\0" "\n" < /proc/$$/cmdline' 0 1 @@ 2`  
`args: 1 Pa55w0rd 2`  
`cmdline:`  
`sh`  
`-c`  
`echo args: "$@" ; echo cmdline: ; tr "\0" "\n" < /proc/$$/cmdline`  
`0`  
`1`  
`@@`  
`2`  

#### Using a Pipeline to Send Secrets

This next example shows `sslpasswd(1)` reading the password from stdin:

`$ keysafe --revoke EXAMPLE-$$`  
`$ keysafe --pipe EXAMPLE -- openssl passwd -noverify -salt xx -stdin </dev/null`  
**`[1]+  Stopped                 keysafe --pipe EXAMPLE -- openssl passwd -noverify -salt xx -stdin < /dev/null`**  
**` unset _KEYSAFE_hDL38 ; read -r _KEYSAFE_hDL38 </proc/455/fd/5 ; fg`**  
`$`  
`$ `**`keysafe -p -s <($_KEYSAFE_hDL38) EXAMPLE-2804 -- openssl passwd -noverify -salt xx -stdin </dev/null`**  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ keysafe -p -s <($_KEYSAFE_hDL38) EXAMPLE-2804 -- openssl passwd -noverify -salt xx -stdin </dev/null`  
`xxU4b0XBMjadY` 

#### Typing Secrets

The final example shows `sslpasswd(1)` reading the password from the controlling terminal:

`$ keysafe --revoke EXAMPLE-$$`  
`$ keysafe --tty EXAMPLE -- openssl passwd -noverify -salt xx`  
**`[1]+  Stopped                 keysafe --tty EXAMPLE -- openssl passwd -noverify -salt xx`**  
**` unset _KEYSAFE_hDS23 ; read -r _KEYSAFE_hDS23 </proc/566/fd/5 ; fg`**  
`$`  
`$ `**`keysafe -t -s <($_KEYSAFE_hDS23) EXAMPLE-2804 -- openssl passwd -noverify -salt xx`**  
**`Memento: ********`**  
`xxU4b0XBMjadY`  
`$ keysafe -t -s <($_KEYSAFE_hDS23) EXAMPLE-2804 -- openssl passwd -noverify -salt xx`  
`xxU4b0XBMjadY` 

This code implements a very simple KVM client (sometimes called a VMM / 
virtual machine monitor) for Linux. It starts a single vCPU virtual machine
with a tiny amount of memory, and then executes a trivial program with it.

The code was developed with the assistance of Anthropic's Sonnet 4.5. I
am unclear on the exact rules (if there are any) for how to license code
developed with AI assistance, but given I normally use Apache2 and the
"assistance" took the form of Google-like search queries and then reading
answers before writing my own code, I am going to run with that here.

This project includes a small amount of code generation to convert the ioctl
definitions from the Linux C header files into a python script. To do that,
do this:

```
cd code_generation
gcc ioctls.c -o ioctls
./ioctls > ../_ioctls
```
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
./ioctls > ../ioctls.py
```

The code is structured like this:

* `pypervisor.py`: the bit you probably want to read, which is the code that
  interacts with KVM.

And then helpers which are kept out of `pypervisor.py` to make this a bit
clearer:

* `displayhelpers.py`: display helpers for the various data structures.
* `ioctls.py`: ioctl magic numbers extracted by the code generation above.
* `structs.py`: the various kernel data structures we need.
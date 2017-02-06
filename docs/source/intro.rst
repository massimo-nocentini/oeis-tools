
************
Introduction
************

This documentation is about a suite of tools to interact with the `Online
Encyclopedia of Integer Sequences <http://oeis.org/>`_ (denoted with
:strong:`OEIS` for short). 

Such suite provides both :emphasis:`programming interfaces` and
:emphasis:`command-line programs` to collect, print and represent connections
among sequences of numbers available in the OEIS, aiming to store data and do
computations locally. In particular, it comprises the following components:

* a :strong:`crawler`, which fetches sequences recursively, implemented with
  :emphasis:`asynchronous` schemas to increase the degree of parallelism and,
  finally, saving data in :emphasis:`json` files; 
* a :strong:`pretty printer`, which parses saved data and shows them in both
  :emphasis:`Markdown` or :emphasis:`ascii` formats, providing filter and
  search capabilities;
* a :strong:`grapher`, which builds graphs according to relations among
  sequences in the sense of :emphasis:`cross-references` OEIS sections.

All the implementation is written in pure Python for flexibility and portability.

.. note:: to run the current version of the :strong:`crawler` it is mandatory
   to have Python 3.6 on the working machine to benefits of latest :literal:`async/await`
   language primitives for asynchronous computations.


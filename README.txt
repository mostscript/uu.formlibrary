Introduction
============

uu.formlibrary is an add-on for Plone that enables the management and
entry of form definitions and form instances.

Form instance types supported include single-record (simple) forms, and
multi-record forms.

This package is originally designed to support forms for healthcare
quality improvement projects, but is not limited to any particular
problem domain.

Features
--------

* Form definitions:
  
  - A library of form definitions can exist in your site for use by
    form instances.  The binding of form instances to definitions is
    done by reference (browsing to the definition) in the edit form
    of the form instance.

  - All definition references are stored as RFC 4122 UUIDs on form
    instance objects.  These references are cataloged such that code
    can query the catalog for all form instances subscribing to a
    definition.

  - Form definitions provide schema for form instances, and provide
    the means for form adminstrators to control, edit the schema
    using simple web-based tools.

* Form instances:

  - All form instances are tied to a definition.

  - All form instances live in a special kind of folder, called a 
    form library.

  - All form instances have optional temporal information: a start
    and stop date distinct from publishing metadata.  By virtue of
    existing indexes for start/stop in Plone's catalog, these are
    searchable in Python code extending this.

* Form types:

  - Simple form -- a single record form.

  - Multi-record form.  Used for chart-audit and similar form types.

    * Multi-record forms are treated as a record container.  These
      expose a JSON API for form submission of multi-form structured
      data payloads (for the bundle of all rows) via JavaScript. The
      Python API for modifying records is a CRUD API built upon a
      container/mapping interface; the JSON API extends this to 
      form submission of a complex data payload.

    * Multi-record forms require JavaScript.

* A workflow for form submission is packaged in uu.workflows, which
  this package depends upon. 


Requires
--------

* Plone 4.1+

* Dexterity (plone.app.dexterity) -- developed against 1.0.3+

* uu.dynamicschema (provides ability to bind persistent chart
  audit entry records to provide user-created dynamic form
  schema).  uu.dynamicschema uses techniques similar to 
  Dexterity, but intended for use in non-content data objects.

    http://bazaar.launchpad.net/~upiq-dev/upiq/uu.dynamicschema

* uu.record -- provides basic non-content record data object 
  interfaces and implementations, including a CRUD controller
  interface using a "record container" pattern. 

    http://bazaar.launchpad.net/~upiq-dev/upiq/uu.record

* uu.workflows -- provides packaged workflows for form and
  intranet workflows, including a form submission workflow
  used by this package.

    http://bazaar.launchpad.net/~upiq-dev/upiq/uu.workflows

--

Author: Sean Upton <sean.upton@hsc.utah.edu>

Copyright 2011, The University of Utah.

Released as free software under the GNU GPL version 2 license.
See doc/COPYING.txt


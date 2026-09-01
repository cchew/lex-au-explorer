# Parity oracle: Corporations Act 2001, Small Business Guide, section 3

- Fixture: `corp-act-s3-sbg.xml`
- eId: `chapter-1__part-1.5__sec-3`
- Source of truth: `lex-au/repo/corpus/docx/corporations-act-2001-c147-vol1.docx`
  (Compilation No. 147, compilation date 1 July 2026), `word/document.xml`
  paragraphs 4432-4479. Text identical in the undated
  `corporations-act-2001-vol1.docx` for this provision.
- legislation.gov.au: `C2004A00818` (compilation `C2026C00339`) / Chapter 1, Part 1.5 ("The Small
  Business Guide"), item 3.

## Why this fixture exists (blocker B1)

Its eId is `chapter-1__part-1.5__sec-3`. Fixture `corp-act-s3.xml` is
`chapter-1__part-1.1__sec-3`. Both end in `sec-3`, both have `<num>3</num>`.
A resolver that suffix-matches a bare `#sec-3` href (or that keys sections by
`num`) has **two** equally valid targets in this one Act. Section numbers are not
unique within an Act; the Small Business Guide re-uses the 1..N numbering.

## Authoritative text

**3  Setting up a new company**

The operators of small businesses can either buy "shelf" companies or set up new
companies themselves.

**3.1 "Shelf" companies**

The operator of a small business may find it more convenient to buy a "shelf"
company (a company that has already been registered but has not traded) from
businesses which set up companies for this purpose or from some legal or
accounting firms.

**3.2 Setting up a company**

To set up a new company themselves, the operator must apply to ASIC for
registration of the company.

A proprietary company limited by shares must have at least 1 shareholder.

To obtain registration, a person must lodge a properly completed application form
with ASIC. The form must set out certain information including details of every
person who has consented to be a shareholder, director or company secretary of
the company.

The company comes into existence when ASIC registers it.

[sections 117-119, 135-136, 140]

**3.3 ACN and name**

When a company is registered, ASIC allocates to it a unique 9 digit number called
the Australian Company Number (ACN). (For use of the ACN see 4.1).

In practice, a new company must have a name that is different from the name of a
company that is already registered. A proprietary company limited by shares must
have the words "Proprietary Limited" as part of its name. Those words can be
abbreviated to "Pty Ltd".

A proprietary company may adopt its ACN as its name. If it does so, its name must
also contain the words "Australian Company Number" (which can be abbreviated to
"ACN"). For example, the company's name might be "ACN 123 456 789 Pty Ltd".

[sections 119, 147-161]

**3.4 Contracts entered into before the company is registered**

A company can ratify a contract entered into by someone on its behalf or for its
benefit before it was registered. If the company does not ratify the contract,
the person who entered into the contract may be personally liable.

[sections 131-133]

**3.5 First shareholders, directors and company secretary**

A person listed with their consent as a shareholder, director or company
secretary in the application for registration of the company becomes a
shareholder, director or company secretary of the company on its registration.

The same person may be both a director of the company and the company secretary.

See 5.1 and 5.2 for directors and 5.4 for company secretaries. See 6.1 for
shareholders.

[section 120]

**3.6 Issuing shares**

It is a replaceable rule (see 1.6) that, before issuing new shares, a company
must first offer them to the existing shareholders in the proportions that the
shareholders already hold. A company may issue shares at a price it determines.

[sections 254B, 254D]

**3.7 Registered office**

A company must have a registered office in Australia and must inform ASIC of the
location of the office. A post office box cannot be the registered office of a
company. The purpose of the registered office is to have a place where all
communications and notices to the company may be sent.

If the company does not occupy the premises where its registered office is
located, the occupier of the premises must agree in writing to having the
company's registered office located there.

A proprietary company is not required to open its registered office to the public
but this does not affect its obligation to make documents available for
inspection.

The company must notify ASIC of any change of address of its registered office.

[sections 100, 142, 143, 173, 1300]

**3.8 Principal place of business**

If a company has a principal place of business that is different from its
registered office, it must notify ASIC of the address of its principal place of
business and of any changes to that address.

[sections 117, 146]

**3.9 Registers kept by the company**

A company must keep registers, including a register of shareholders. A company
must keep its registers at:

- the company's registered office; or
- the company's principal place of business; or
- a place (whether on premises of the company or of someone else) where the work
  in maintaining the register is done; or
- another place approved by ASIC.

A register may be kept either in a bound or looseleaf book or on computer.

If a register is kept on computer, its contents must be capable of being printed
out in hard copy.

[sections 172, 1300, 1301, 1306]

**3.10 Register of shareholders**

A company must keep in its register of shareholders such information as:

- the names and addresses of its shareholders; and
- details of shares held by individual shareholders.

[sections 168-169]

## Structure notes

- Flat `<section>` with a single `<content>` holding ~45 sibling `<p>` elements.
  No `<subsection>`/`<paragraph>` machinery at all - the "3.1", "3.2" ... marks
  are literal text at the start of a `<p>`, not `<num>` elements.
- Bulleted lists (3.9, 3.10) are `<p>` elements each beginning with a literal
  bullet character `•` + tab.
- Cross-reference pointers are almost all plain text in square brackets, e.g.
  `[sections 117-119, 135-136, 140]`. Only two are marked up:
  `<ref href="#sec-120">section 120</ref>` (item 3.5) and there is no other
  `<ref>` in the subtree. A renderer keyed on `<ref>` will link 1 of ~12
  cross-reference clusters here.
- En dashes in the source ("117-119") are U+2014 em dashes in the docx and XML;
  digits are grouped with non-breaking spaces ("123 456 789").
- No authorial notes, no tables, no figures.

"use strict";

// E4: record class and the agreement a client record is received under.
//
// Two classes. SCOPING is received under a mutual NDA before any contract, so
// a client can get a quote. STUDY is received only after a countersigned MSA
// and Order Form. No record may exist without the agreement reference that
// makes holding it lawful, and that is enforced here, at construction: the
// store accepts only a basis this module issued, and this module issues one
// only for a complete, well-formed set of references. A record without one is
// not rejected later; it cannot be built.
//
// References are opaque operator identifiers for agreements held elsewhere.
// No agreement text, party name or term is ever stored here, and none is in the
// repository: the reference format is shape, the references are instances.

const ISSUED = new WeakSet();
const BRAND = Symbol("carbon.private-team-intake.record-basis");
const REFERENCE = /^[A-Za-z0-9][A-Za-z0-9._:\/-]{2,127}$/;

class RecordBasis {
  constructor(brand, fields) {
    if (brand !== BRAND)
      throw Error("A record basis can only be issued for a complete set of agreement references");
    Object.assign(this, fields);
    Object.freeze(this.agreements);
    Object.freeze(this);
    ISSUED.add(this);
  }
}

function reference(value, label) {
  if (typeof value !== "string" || !REFERENCE.test(value))
    throw Error(`A ${label} reference is required: an opaque identifier for an agreement held outside this store`);
  return value;
}

/** A SCOPING record: received under a mutual NDA, before any contract. */
function scopingBasis({ nda } = {}) {
  const ndaRef = reference(nda, "mutual NDA");
  return new RecordBasis(BRAND, {
    record_class: "SCOPING",
    agreements: { nda: ndaRef },
    legal_basis: "contract:" + ndaRef,
  });
}

/** A STUDY record: only after a countersigned MSA and an Order Form under it. */
function studyBasis({ msa, order_form: orderForm } = {}) {
  const msaRef = reference(msa, "countersigned MSA");
  const orderRef = reference(orderForm, "Order Form");
  return new RecordBasis(BRAND, {
    record_class: "STUDY",
    agreements: { msa: msaRef, order_form: orderRef },
    legal_basis: "contract:" + msaRef + "/" + orderRef,
  });
}

/** True only for a basis this module issued. A copied literal is not one. */
function isRecordBasis(value) {
  return typeof value === "object" && value !== null && ISSUED.has(value);
}

/** The stored form of an issued basis. */
function stored(basis) {
  if (!isRecordBasis(basis)) throw Error("A record cannot be created without an agreement reference");
  return {
    record_class: basis.record_class,
    agreements: { ...basis.agreements },
    legal_basis: basis.legal_basis,
  };
}

/**
 * The basis a relayed request carries, from its headers, never from the
 * package: the package bytes are the client's and are stored exactly.
 */
function basisFromHeaders(headers) {
  const recordClass = headers["x-carbon-record-class"];
  if (recordClass === "SCOPING") return scopingBasis({ nda: headers["x-carbon-nda-ref"] });
  if (recordClass === "STUDY")
    return studyBasis({ msa: headers["x-carbon-msa-ref"], order_form: headers["x-carbon-order-form-ref"] });
  throw Error("A record class is required: SCOPING (with an NDA reference) or STUDY (with MSA and Order Form references)");
}

module.exports = { RecordBasis, basisFromHeaders, isRecordBasis, scopingBasis, stored, studyBasis };

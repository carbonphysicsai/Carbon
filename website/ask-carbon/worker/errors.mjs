export class PublicApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "PublicApiError";
    this.status = status;
    this.code = code;
  }
}

const encoder = new TextEncoder();

const constantTimeEqual = (left, right) => {
  if (typeof left !== "string" || typeof right !== "string") return false;
  const leftBytes = encoder.encode(left);
  const rightBytes = encoder.encode(right);
  let difference = leftBytes.length ^ rightBytes.length;
  const length = Math.max(leftBytes.length, rightBytes.length);
  for (let index = 0; index < length; index += 1) difference |= (leftBytes[index] ?? 0) ^ (rightBytes[index] ?? 0);
  return difference === 0;
};

export const stagingRequestAuthorized = (request, env) => (
  typeof env.ASK_CARBON_STAGING_BASIC_AUTH === "string" &&
  env.ASK_CARBON_STAGING_BASIC_AUTH.length >= 16 &&
  constantTimeEqual(
    request.headers.get("authorization"),
    `Basic ${env.ASK_CARBON_STAGING_BASIC_AUTH}`,
  )
);

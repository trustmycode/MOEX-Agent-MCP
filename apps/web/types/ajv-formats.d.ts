declare module "ajv-formats" {
  import type Ajv from "ajv";

  const addFormats: (ajv: Ajv) => Ajv;
  export default addFormats;
}


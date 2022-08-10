import type { AxiosResponse } from "axios";

export const processResponse = <T>(response: AxiosResponse<T>): T => {
  if (response.status < 200 || response.status > 299) {
    throw new Error(`Unable to fetch: ${response.statusText}`);
  } else {
    return response.data;
  }
};

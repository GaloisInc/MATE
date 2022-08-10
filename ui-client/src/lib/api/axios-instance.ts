import axios from "axios";
import type { AxiosInstance } from "axios";

const AXIOS_TIMEOUT_MS = 10 * 60 * 1000; // Give server 10 minutes to respond
const axiosInstance: AxiosInstance = axios.create();
axiosInstance.defaults.timeout = AXIOS_TIMEOUT_MS;

export { axiosInstance, AXIOS_TIMEOUT_MS };

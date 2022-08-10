import { renderHook } from "@testing-library/react-hooks";
import { usePage } from "./usePage";

describe("usePage", () => {
  describe("isLoading", () => {
    test("should have a default state that indicates we are not loading", () => {
      const { result } = renderHook(() => usePage());

      expect(result.current.isLoading).toBeFalsy();
    });
  });

  describe("loading message", () => {
    test("should return the default loading message if not given an override", () => {
      const { result } = renderHook(() => usePage());

      expect(result.current.loadingMessage).toBe("Loading...");
    });

    test("should return the loading message we pass in", () => {
      const { result } = renderHook(() => usePage({ message: "TEST LOADING" }));

      expect(result.current.loadingMessage).toBe("TEST LOADING");
    });
  });
});

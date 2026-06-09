import {
  deleteConversation,
  shouldResetChatAfterDelete,
} from "./chatHistory";

jest.mock("../config/api", () => ({
  apiFetch: jest.fn(),
  authFetch: jest.fn(),
}));

const { apiFetch, authFetch } = require("../config/api");

describe("shouldResetChatAfterDelete", () => {
  it("returns true when conversation id matches active conversation", () => {
    const conversation = { id: "conv-1", external_session_key: "thread_a" };
    expect(
      shouldResetChatAfterDelete(conversation, {
        activeConversationId: "conv-1",
        chatThreadId: "thread_b",
      }),
    ).toBe(true);
  });

  it("returns true when external session key matches active thread", () => {
    const conversation = { id: "conv-2", external_session_key: "thread_a" };
    expect(
      shouldResetChatAfterDelete(conversation, {
        activeConversationId: "conv-1",
        chatThreadId: "thread_a",
      }),
    ).toBe(true);
  });

  it("returns false for unrelated conversation", () => {
    const conversation = { id: "conv-2", external_session_key: "thread_b" };
    expect(
      shouldResetChatAfterDelete(conversation, {
        activeConversationId: "conv-1",
        chatThreadId: "thread_a",
      }),
    ).toBe(false);
  });
});

describe("deleteConversation", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    authFetch.mockReset();
    apiFetch.mockResolvedValue({ status: "deleted" });
    authFetch.mockResolvedValue({ status: "cleared" });
  });

  it("calls DELETE /conversations/{id}", async () => {
    await deleteConversation("abc-123");
    expect(apiFetch).toHaveBeenCalledWith("/conversations/abc-123", {
      method: "DELETE",
    });
    expect(authFetch).not.toHaveBeenCalled();
  });

  it("best-effort clears gateway session when external key provided", async () => {
    await deleteConversation("abc-123", { externalSessionKey: "thread_xyz" });
    expect(authFetch).toHaveBeenCalledWith("/session/thread_xyz", {
      method: "DELETE",
    });
  });
});

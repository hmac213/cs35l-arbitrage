import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DashboardLayout from "@/app/dashboard/layout";
import { supabase } from "@/lib/supabase";

// Get mocked functions
const mockGetUser = supabase.auth.getUser as jest.Mock;
const mockSignOut = supabase.auth.signOut as jest.Mock;
const mockOnAuthStateChange = supabase.auth.onAuthStateChange as jest.Mock;

// Mock useRouter
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}));

describe("DashboardLayout", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOnAuthStateChange.mockReturnValue({
      data: { subscription: { unsubscribe: jest.fn() } },
    });
  });

  it("shows loading state initially", () => {
    mockGetUser.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("redirects to login when not authenticated", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/");
    });
  });

  it("displays user name when authenticated", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: { full_name: "John Doe" },
        },
      },
    });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });
  });

  it("displays email when full_name is not available", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: {},
        },
      },
    });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });
  });

  it("renders logout button", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: { full_name: "John Doe" },
        },
      },
    });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
    });
  });

  it("calls signOut and redirects on logout", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: { full_name: "John Doe" },
        },
      },
    });
    mockSignOut.mockResolvedValue({});

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
    });

    const logoutButton = screen.getByRole("button", { name: /log out/i });
    fireEvent.click(logoutButton);

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith("/");
    });
  });

  it("renders children when authenticated", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: { full_name: "John Doe" },
        },
      },
    });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });
  });

  it("renders header with dashboard title", async () => {
    mockGetUser.mockResolvedValue({
      data: {
        user: {
          id: "123",
          email: "test@example.com",
          user_metadata: { full_name: "John Doe" },
        },
      },
    });

    render(
      <DashboardLayout>
        <div>Dashboard Content</div>
      </DashboardLayout>
    );

    await waitFor(() => {
      expect(screen.getByText("Arbitrage Dashboard")).toBeInTheDocument();
    });
  });
});

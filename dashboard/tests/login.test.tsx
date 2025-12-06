import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/page";
import { supabase } from "@/lib/supabase";

// Get mocked functions
const mockSignInWithPassword = supabase.auth.signInWithPassword as jest.Mock;
const mockSignInWithOAuth = supabase.auth.signInWithOAuth as jest.Mock;

describe("LoginPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the login form", () => {
    render(<LoginPage />);

    expect(screen.getByText("Sign in to")).toBeInTheDocument();
    expect(screen.getByText("Arbitrage")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue$/i })).toBeInTheDocument();
  });

  it("renders the Google sign-in button", () => {
    render(<LoginPage />);

    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("renders link to signup page", () => {
    render(<LoginPage />);

    expect(screen.getByText("Sign up")).toBeInTheDocument();
  });

  it("allows user to type email and password", () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email address");
    const passwordInput = screen.getByLabelText("Password");

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });

    expect(emailInput).toHaveValue("test@example.com");
    expect(passwordInput).toHaveValue("password123");
  });

  it("toggles password visibility", () => {
    render(<LoginPage />);

    const passwordInput = screen.getByLabelText("Password");
    const toggleButton = screen.getByRole("button", { name: "" }); // The eye icon button

    expect(passwordInput).toHaveAttribute("type", "password");

    // Find the toggle button (it's the button inside the password div)
    const passwordContainer = passwordInput.parentElement;
    const toggleBtn = passwordContainer?.querySelector("button");
    if (toggleBtn) {
      fireEvent.click(toggleBtn);
      expect(passwordInput).toHaveAttribute("type", "text");

      fireEvent.click(toggleBtn);
      expect(passwordInput).toHaveAttribute("type", "password");
    }
  });

  it("submits form with email and password", async () => {
    mockSignInWithPassword.mockResolvedValue({ error: null });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email address");
    const passwordInput = screen.getByLabelText("Password");
    const submitButton = screen.getByRole("button", { name: /continue$/i });

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSignInWithPassword).toHaveBeenCalledWith({
        email: "test@example.com",
        password: "password123",
      });
    });
  });

  it("displays error message on login failure", async () => {
    mockSignInWithPassword.mockResolvedValue({
      error: { message: "Invalid email or password" },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email address");
    const passwordInput = screen.getByLabelText("Password");
    const submitButton = screen.getByRole("button", { name: /continue$/i });

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "wrongpassword" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText("Invalid email or password")).toBeInTheDocument();
    });
  });

  it("shows loading state during submission", async () => {
    mockSignInWithPassword.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ error: null }), 100))
    );

    render(<LoginPage />);

    const emailInput = screen.getByLabelText("Email address");
    const passwordInput = screen.getByLabelText("Password");
    const submitButton = screen.getByRole("button", { name: /continue$/i });

    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.click(submitButton);

    expect(screen.getByText("Signing in...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Signing in...")).not.toBeInTheDocument();
    });
  });

  it("calls Google OAuth on Google button click", async () => {
    mockSignInWithOAuth.mockResolvedValue({ error: null });

    render(<LoginPage />);

    const googleButton = screen.getByRole("button", { name: /continue with google/i });
    fireEvent.click(googleButton);

    await waitFor(() => {
      expect(mockSignInWithOAuth).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo: expect.stringContaining("/dashboard"),
        },
      });
    });
  });

  it("displays error message on Google OAuth failure", async () => {
    mockSignInWithOAuth.mockResolvedValue({
      error: { message: "OAuth error occurred" },
    });

    render(<LoginPage />);

    const googleButton = screen.getByRole("button", { name: /continue with google/i });
    fireEvent.click(googleButton);

    await waitFor(() => {
      expect(screen.getByText("OAuth error occurred")).toBeInTheDocument();
    });
  });
});

import { render, screen, fireEvent } from "@testing-library/react";
import { BudgetInput } from "@/components/BudgetInput";

describe("BudgetInput Component", () => {
  it("should render with empty input initially", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("should display budget value when provided", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={100} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget") as HTMLInputElement;
    expect(input.value).toBe("100");
  });

  it("should call onBudgetChange when user types valid number", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    fireEvent.change(input, { target: { value: "100" } });

    expect(mockOnChange).toHaveBeenCalledWith(100);
  });

  it("should handle decimal input", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    fireEvent.change(input, { target: { value: "100.50" } });

    expect(mockOnChange).toHaveBeenCalledWith(100.5);
  });

  it("should call onBudgetChange with null when input is cleared", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={100} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    fireEvent.change(input, { target: { value: "" } });

    expect(mockOnChange).toHaveBeenCalledWith(null);
  });

  it("should show clear button when budget is set", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={100} onBudgetChange={mockOnChange} />);

    const clearButton = screen.getByLabelText(/clear budget/i);
    expect(clearButton).toBeInTheDocument();
  });

  it("should not show clear button when budget is null", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const clearButton = screen.queryByLabelText(/clear budget/i);
    expect(clearButton).not.toBeInTheDocument();
  });

  it("should clear budget when clear button is clicked", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={100} onBudgetChange={mockOnChange} />);

    const clearButton = screen.getByLabelText(/clear budget/i);
    fireEvent.click(clearButton);

    expect(mockOnChange).toHaveBeenCalledWith(null);
  });

  it("should handle invalid input gracefully", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    fireEvent.change(input, { target: { value: "abc" } });

    // Should call with null for invalid input
    expect(mockOnChange).toHaveBeenCalledWith(null);
  });

  it("should strip non-numeric characters except decimal point", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByLabelText("Your Budget");
    fireEvent.change(input, { target: { value: "$100.50" } });

    expect(mockOnChange).toHaveBeenCalledWith(100.5);
  });

  it("should display placeholder text", () => {
    const mockOnChange = jest.fn();
    render(<BudgetInput budget={null} onBudgetChange={mockOnChange} />);

    const input = screen.getByPlaceholderText("Enter your budget");
    expect(input).toBeInTheDocument();
  });
});


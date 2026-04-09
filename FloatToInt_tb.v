module FloatToInt_tb;
    reg clk;
    reg ce;
    reg [31:0] i;
    wire [31:0] o;
    wire overflow;
    integer j;

    FloatToInt #(32) uut (.clk(clk), .ce(ce), .i(i), .o(o), .overflow(overflow));

    initial begin
        clk = 0;
        ce = 1;
        $display("Running robust simulation for FloatToInt...");
        
        // Test cases
        i = 32'h42C80000; // 100.0
        #20;
        $display("i=%h (100.0) | o=%h | overflow=%b", i, o, overflow);

        i = 32'hC2C80000; // -100.0
        #20;
        $display("i=%h (-100.0) | o=%h | overflow=%b", i, o, overflow);

        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            #20;
            $display("i=%h | o=%h | overflow=%b", i, o, overflow);
        end
        
        $display("Simulation for FloatToInt finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule

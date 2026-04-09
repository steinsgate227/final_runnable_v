module IntToFloat_tb;
    parameter WID = 32;
    reg clk;
    reg ce;
    reg [2:0] rm;
    reg [WID-1:0] i;
    wire [WID-1:0] o;
    integer j;

    IntToFloat #(WID) uut (.clk(clk), .ce(ce), .rm(rm), .i(i), .o(o));

    initial begin
        clk = 0;
        ce = 1;
        rm = 3'b000;
        i = 0;
        $display("Running robust simulation for IntToFloat...");
        
        // Fixed cases
        i = 32'd1000; #20;
        $display("i=%d (1000) | o=%h", i, o);

        i = -32'd1000; #20;
        $display("i=%d (-1000) | o=%h", i, o);

        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            #20;
            $display("i=%d | o=%h", i, o);
        end
        
        $display("Simulation for IntToFloat finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule

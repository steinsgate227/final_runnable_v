module fpdivr2_tb;
    parameter WID = 16;
    reg clk;
    reg ld;
    reg [WID-1:0] a, b;
    wire [WID*2-1:0] q;
    wire [WID-1:0] r;
    wire done;
    wire [7:0] lzcnt;
    integer j;

    fpdivr2 #(WID) uut (.clk4x(clk), .ld(ld), .a(a), .b(b), .q(q), .r(r), .done(done), .lzcnt(lzcnt));

    initial begin
        clk = 0;
        ld = 0;
        a = 0;
        b = 0;
        $display("Running robust simulation for fpdivr2...");
        
        #100;
        
        for (j = 0; j < 10; j = j + 1) begin
            wait(done == 1);
            @(posedge clk);
            a = $random;
            b = $random % 100 + 1; // avoid divide by zero if it's raw int
            ld = 1;
            @(posedge clk);
            ld = 0;
            $display("Test Case %0d: a=%d | b=%d", j, a, b);
            
            wait(done == 1);
            $display("Result: q=%h | r=%h", q, r);
            #100;
        end
        
        $display("Simulation for fpdivr2 finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule

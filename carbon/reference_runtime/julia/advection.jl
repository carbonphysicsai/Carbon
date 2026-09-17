# Fixed reviewed public DEVELOPMENT instrument, executed by the existing carrier.
# Nodal upwind Euler differences; fine initial values use periodic linear interpolation.
const METHOD = "julia_periodic_advection_upwind_refinement_v1"
const UNITS = "carbon_advection_definition_native_v1"
const LAYOUT = "time,x;C;<f8;point_estimate;periodic"
const CFL = 0.75
const MAX_STEPS = 200000

function request()
    VERSION == v"1.13.0" || error("runtime")
    raw = open(io -> read(io, 32769), "request.txt", "r")
    length(raw) <= 32768 || error("bytes")
    isascii(String(copy(raw))) || error("encoding")
    fields = split(String(raw), '\n'; keepempty=true)
    length(fields) == 14 && fields[end] == "" || error("framing")
    fields[1] == "CARBON_JULIA_ADVECTION_REQUEST_V1" || error("schema")
    fields[2] == METHOD && fields[3] == "1.13.0" || error("method")
    all(occursin(r"^sha256:[0-9a-f]{64}$", fields[i]) for i in (4,5,13)) || error("identity")
    fields[6] == UNITS && fields[7] == LAYOUT || error("units/layout")
    L, c = parse.(Float64, fields[8:9])
    n = parse(Int, fields[10])
    initial = parse.(Float64, split(fields[11], ','))
    times = parse.(Float64, split(fields[12], ','))
    16 <= n <= 512 && ispow2(n) && length(initial) == n || error("shape")
    1 <= length(times) <= 64 && all(t -> isfinite(t) && t >= 0, times) || error("time")
    all(isfinite, initial) && isfinite(L) && L > 0 && isfinite(c) || error("finite")
    dx = L / (2n)
    dx > 0 && isfinite(abs(c)/dx) || error("scale")
    maximum(times) * abs(c) / dx / CFL + length(times) <= MAX_STEPS || error("work")
    return (; L, c, n, initial, times, identity=String(fields[13]))
end

function solve(r, factor)
    n = r.n * factor
    state = factor == 1 ? copy(r.initial) : [
        isodd(i) ? r.initial[div(i+1,2)] :
        0.5*r.initial[div(i,2)] + 0.5*r.initial[div(i,2) == r.n ? 1 : div(i,2)+1]
        for i in 1:n]
    initial_mean = sum(state)/n
    isfinite(initial_mean) || error("mean")
    buffer = similar(state)
    values = Matrix{Float64}(undef, length(r.times), r.n)
    current, drift, steps = 0.0, 0.0, 0
    for row in sortperm(r.times)
        target = r.times[row]
        while current < target
            steps < MAX_STEPS || error("work")
            remaining = target-current
            dt = r.c == 0 ? remaining : min(remaining, CFL*(r.L/n)/abs(r.c))
            isfinite(dt) && dt > 0 && current+dt > current || error("time step")
            ratio = abs(r.c)*dt/(r.L/n)
            0 <= ratio <= 1 || error("CFL")
            for i in 1:n
                upstream = r.c >= 0 ? (i == 1 ? n : i-1) : (i == n ? 1 : i+1)
                buffer[i] = (1-ratio)*state[i] + ratio*state[upstream]
            end
            state, buffer = buffer, state
            all(isfinite, state) || error("numerical")
            drift = max(drift, abs(sum(state)/n-initial_mean))
            current = dt == remaining ? target : current+dt
            steps += 1
        end
        for column in 1:r.n
            values[row,column] = state[1+(column-1)*factor]
        end
    end
    return values, drift, steps
end

function output_array(name, values)
    open("/scratch/output/" * name, "w") do io
        for row in axes(values,1), column in axes(values,2)
            write(io, htol(reinterpret(UInt64, values[row,column])))
        end
    end
end

function main()
    r = request()
    observed = @timed begin
        coarse, coarse_drift, coarse_steps = solve(r, 1)
        fine, fine_drift, fine_steps = solve(r, 2)
        difference = fine - coarse
        rms = sqrt(sum(abs2, difference)/length(difference))
        largest = maximum(abs, difference)
        all(isfinite, (coarse_drift, fine_drift, rms, largest)) || error("diagnostic")
        (; coarse, fine, coarse_drift, fine_drift, coarse_steps, fine_steps, rms, largest)
    end
    value = observed.value
    output_array("coarse.f64le", value.coarse)
    output_array("fine.f64le", value.fine)
    open("/scratch/output/result.json", "w") do io
        print(io, "{\"schema\":\"carbon.julia.advection-result.v1\",\"method\":\"", METHOD,
            "\",\"request_digest\":\"", r.identity, "\",\"units\":\"", UNITS,
            "\",\"layout\":\"", LAYOUT, "\",\"shape\":[", length(r.times), ",", r.n,
            "],\"coarse_points\":", r.n, ",\"fine_points\":", 2 * r.n,
            ",\"coarse_steps\":", value.coarse_steps, ",\"fine_steps\":", value.fine_steps,
            ",\"coarse_mean_drift\":", value.coarse_drift, ",\"fine_mean_drift\":", value.fine_drift,
            ",\"refinement_rms\":", value.rms, ",\"refinement_max\":", value.largest,
            ",\"completed_horizon\":", maximum(r.times), ",\"solver_seconds\":", observed.time,
            ",\"allocated_bytes\":", observed.bytes, "}")
    end
end

try
    main()
catch
    exit(20)
end
